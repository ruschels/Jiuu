import streamlit as st
import os
import random
import unicodedata
import requests
import time
import json
import re
import math
from PIL import Image, ImageGrab, ImageFilter
from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip
from google import genai
from google.genai import types

# ==========================================
# CONFIGURAÇÕES E CHAVES
# ==========================================
#CHAVE_GEMINI_PADRAO = 
#MODELO_GEMINI = 
#API_FISH = 
#VOZ_MATHEUS = 

# ==========================================
# FUNÇÕES DE LÓGICA E IA
# ==========================================
def chamar_gemini_com_retry(prompt, api_key, max_tentativas_por_modelo=3, delay_segundos=4):
    """
    Tenta acessar a IA usando uma lista de modelos (fallback) e exibe logs visuais em tempo real.
    Lógica idêntica ao gabi.py
    """
    modelos_fallback = [
        MODELO_GEMINI,               # Primeira tentativa: gemini-flash-latest
        "gemini-3.6-flash",          # Segunda tentativa: 3.6
        "gemini-1.5-flash-8b",       # Fallback extra 1
        "gemini-1.5-pro"             # Fallback extra 2
    ]
    
    client = genai.Client(api_key=api_key)
    log_container = st.empty()
    
    for modelo in modelos_fallback:
        for tentativa in range(max_tentativas_por_modelo):
            log_container.info(f"🔄 Tentando conectar ao modelo: **{modelo}** (Tentativa {tentativa + 1}/{max_tentativas_por_modelo})...")
            
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                
                log_container.success(f"✅ Sucesso! O modelo **{modelo}** processou a requisição e retornou os dados.")
                time.sleep(1)
                log_container.empty() # Limpa o log após sucesso
                return response.text
                
            except Exception as e:
                erro_str = str(e)
                if "503" in erro_str or "429" in erro_str:
                    log_container.warning(f"⚠️ **{modelo}** sobrecarregado. Aguardando {delay_segundos}s para tentar de novo...")
                    if tentativa < max_tentativas_por_modelo - 1:
                        time.sleep(delay_segundos)
                        continue
                    else:
                        break 
                else:
                    log_container.error(f"❌ Erro no **{modelo}**: {erro_str[:80]}... Pulando para o próximo.")
                    time.sleep(2) 
                    break 
                    
    log_container.error("❌ Todos os modelos falharam. A rede da IA está completamente congestionada.")
    raise Exception(f"Falha de conexão em todas as rotas. Tente novamente mais tarde.")

def gerar_audio_fishaudio(texto, output_path, api_key, voice_id):
    """Envia o texto para a API do Fish Audio e salva o MP3 gerado."""
    url = "https://api.fish.audio/v1/tts"
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json"
    }
    # O payload segue a estrutura exigida pelo Fish Audio
    payload = {
        "text": texto, 
        "reference_id": voice_id, 
        "format": "mp3"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            with open(output_path, "wb") as f: 
                f.write(response.content)
            return output_path, None
        else:
            return None, f"Status {response.status_code}: {response.text}"
    except Exception as e:
        return None, f"Erro de Conexão: {str(e)}"


def normalizar_texto(texto):
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto.lower().strip()

def obter_timestamps_deepgram(caminho_audio, api_key):
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=pt-BR&punctuate=true"
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "audio/mpeg"}
    with open(caminho_audio, "rb") as audio:
        response = requests.post(url, headers=headers, data=audio)
    if response.status_code == 200:
        return response.json()['results']['channels'][0]['alternatives'][0]['words']
    else:
        st.error(f"Erro no Deepgram: {response.text}")
        return []

def criar_clip_vertical_com_blur(caminho_arquivo, duracao):
    """Lê uma imagem, preenche o fundo 1080x1920 com blur e centraliza a original."""
    img_original = Image.open(caminho_arquivo).convert("RGB")
    w_orig, h_orig = img_original.size
    
    # 1. Cria o fundo borrado (Cover)
    ratio_bg = max(1080 / w_orig, 1920 / h_orig)
    new_w_bg = int(w_orig * ratio_bg)
    new_h_bg = int(h_orig * ratio_bg)
    bg_img = img_original.resize((new_w_bg, new_h_bg), Image.Resampling.LANCZOS)
    
    # Crop no centro para ficar exatamente 1080x1920
    left = (new_w_bg - 1080) / 2
    top = (new_h_bg - 1920) / 2
    bg_img = bg_img.crop((left, top, left + 1080, top + 1920))
    
    # Aplica o Blur pesado para o fundo
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=40))
    
    # 2. Redimensiona a imagem principal para caber na tela (Contain)
    ratio_fg = min(1080 / w_orig, 1920 / h_orig)
    new_w_fg = int(w_orig * ratio_fg)
    new_h_fg = int(h_orig * ratio_fg)
    fg_img = img_original.resize((new_w_fg, new_h_fg), Image.Resampling.LANCZOS)
    
    # Cola a imagem principal sobre o fundo borrado
    pos_x = (1080 - new_w_fg) // 2
    pos_y = (1920 - new_h_fg) // 2
    bg_img.paste(fg_img, (pos_x, pos_y))
    
    # Converte para ImageClip do MoviePy
    import numpy as np
    return ImageClip(np.array(bg_img)).set_duration(duracao)


def gerar_video(caminho_audio, palavras_deepgram, pasta_base, animacao="Zoom In", transicao="Crossfade", output_name="video_jiujitsu.mp4"):
    pastas_disponiveis = [d for d in os.listdir(pasta_base) if os.path.isdir(os.path.join(pasta_base, d))]
    mapa_pastas = {normalizar_texto(p): p for p in pastas_disponiveis}
    timeline = []
    
    # Mapeia as imagens
    for item in palavras_deepgram:
        palavra_limpa = normalizar_texto(item['word'])
        if palavra_limpa in mapa_pastas:
            caminho_pasta = os.path.join(pasta_base, mapa_pastas[palavra_limpa])
            arquivos = [f for f in os.listdir(caminho_pasta) if f.endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov'))]
            if arquivos:
                media_escolhida = random.choice(arquivos)
                timeline.append({"keyword": palavra_limpa, "start": item['start'], "file": os.path.join(caminho_pasta, media_escolhida)})
    
    if not timeline:
        return None

    audio = AudioFileClip(caminho_audio)
    clips_visuais = []
    
    # Fundo preto inicial caso o áudio comece vazio
    if timeline[0]['start'] > 0:
        clips_visuais.append(ColorClip(size=(1080, 1920), color=(0,0,0)).set_duration(timeline[0]['start']))

    for i, cena in enumerate(timeline):
        start_time = cena['start']
        end_time = timeline[i+1]['start'] if i + 1 < len(timeline) else audio.duration
        
        # Lógica de sobreposição para a transição Crossfade
        overlap = 0.3 if transicao == "Crossfade (Suave)" and i > 0 else 0
        start_time_ajustado = max(0, start_time - overlap)
        duracao = (end_time - start_time) + overlap
        
        caminho_arquivo = cena['file']
        
        if caminho_arquivo.endswith(('.mp4', '.mov')):
            clip = VideoFileClip(caminho_arquivo).loop(duration=duracao)
            # Para vídeos, ajustamos a largura e centralizamos (o fundo fica preto)
            clip = clip.resize(width=1080).set_position('center').set_start(start_time_ajustado)
        else:
            # Para imagens, usamos a nova função de fundo desfocado
            clip = criar_clip_vertical_com_blur(caminho_arquivo, duracao).set_start(start_time_ajustado)
            
        # APLICAÇÃO DA ANIMAÇÃO DINÂMICA
        if animacao == "Zoom In Suave":
            clip = clip.resize(lambda t: 1 + 0.03 * t).set_position(('center', 'center'))
        elif animacao == "Zoom Out Suave":
            clip = clip.resize(lambda t: 1.15 - 0.03 * t).set_position(('center', 'center'))
            
        # APLICAÇÃO DA TRANSIÇÃO
        if overlap > 0:
            clip = clip.crossfadein(overlap)
            
        clips_visuais.append(clip)
        
    video_final = CompositeVideoClip(clips_visuais, size=(1080, 1920)).set_audio(audio)
    
    with st.spinner('Renderizando vídeo cinematográfico...'):
        video_final.write_videofile(output_name, fps=30, codec="libx264", audio_codec="aac")
    return output_name

# Garante que as pastas base existem
pasta_base = "imagens_jiu"
if not os.path.exists(pasta_base):
    os.makedirs(pasta_base)
if not os.path.exists("roteiros"):
    os.makedirs("roteiros")

# ==========================================
# INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="App de Jiu-Jitsu Studio", layout="wide")
st.title("🥋 App de Jiu-Jitsu Studio")

tab1, tab2, tab3 = st.tabs(["📝 Geração de Roteiro (Gemini)", "🎬 Gerador de Vídeo", "📁 Gerenciador de Pastas (Mídia)"])

# ==========================================
# ABA 1: GERAÇÃO DE ROTEIRO (GEMINI)
# ==========================================
with tab1:
    st.header("Gerar Roteiro com IA (Gemini)")
    st.write("A IA vai criar um roteiro fluido usando exclusivamente os termos das pastas que você já tem no sistema.")
    
    col_ai1, col_ai2 = st.columns(2)
    with col_ai1:
        api_gemini = st.text_input("API Key do Gemini", value=CHAVE_GEMINI_PADRAO, type="password")
        tema_video = st.text_input("Tema do vídeo", placeholder="Ex: Combinações a partir da guarda fechada")
    
    with col_ai2:
        pastas_atuais = [d for d in os.listdir(pasta_base) if os.path.isdir(os.path.join(pasta_base, d))]
        st.write("📦 **Termos disponíveis (Pastas atuais):**")
        st.caption(", ".join(pastas_atuais) if pastas_atuais else "Nenhuma pasta criada ainda.")

    if st.button("✨ Gerar Estrutura (JSON)", type="primary"):
        if not api_gemini:
            st.error("Por favor, insira a chave da API do Gemini.")
        elif not pastas_atuais:
            st.warning("Você precisa criar pastas na aba 'Gerenciador de Pastas' primeiro!")
        elif not tema_video:
            st.warning("Digite um tema para o vídeo.")
        else:
            with st.spinner(f"Criando roteiro fluido sobre '{tema_video}'..."):
                termos_str = ", ".join(pastas_atuais)
                
                prompt = f"""
                Você é um especialista em Jiu-Jitsu e criador de conteúdo para Reels/TikTok.
                Crie um roteiro de vídeo curto e MUITO FLUIDO sobre o tema: '{tema_video}'.
                
                DIRETRIZES DE TOM DE VOZ E FLUIDEZ:
                - O tom deve ser de uma conversa entre parceiros de treino ou uma explicação clara para um aluno.
                - Fale de forma pausada, segura e didática.
                - Vá direto ao ponto técnico.
                
                REGRA OBRIGATÓRIA: Você DEVE incluir naturalmente no texto da narração alguns dos seguintes termos: 
                {termos_str}.
                
                A saída DEVE ser estritamente em JSON, seguindo a estrutura abaixo.
                Na chave 'palavras_chave', inclua APENAS os nomes exatos das pastas/termos que você usou no roteiro.
                
                {{
                    "titulo": "Título chamativo do vídeo",
                    "texto": "Texto narrado do vídeo...",
                    "palavras_chave": ["termo1", "termo2"]
                }}
                """
                
                try:
                    # Usando a função idêntica ao gabi.py
                    roteiro_texto = chamar_gemini_com_retry(prompt, api_key=api_gemini)
                    
                    # Garantir limpeza caso a IA retorne blocos Markdown
                    if roteiro_texto.startswith("```json"):
                        roteiro_texto = roteiro_texto[7:-3]
                    elif roteiro_texto.startswith("```"):
                        roteiro_texto = roteiro_texto[3:-3]
                        
                    json_roteiro = json.loads(roteiro_texto)
                    
                    nome_limpo = re.sub(r'[^\w\-]', '_', tema_video).lower()
                    caminho_salvar = os.path.join("roteiros", f"roteiro_{nome_limpo}.json")
                    
                    with open(caminho_salvar, "w", encoding="utf-8") as f:
                        json.dump(json_roteiro, f, indent=4, ensure_ascii=False)
                        
                    st.success(f"Roteiro gerado e salvo como '{caminho_salvar}'!")
                    st.json(json_roteiro)
                    
                except Exception as e:
                    st.error(f"Erro no Gemini: {e}")

# ==========================================
# ABA 2: GERADOR DE VÍDEO
# ==========================================
# ==========================================
# ABA 2: GERADOR DE VÍDEO (FLUXO COMPLETO)
# ==========================================
with tab2:
    st.header("Sincronizar Áudio e Gerar Vídeo")
    
    roteiros_disponiveis = [f for f in os.listdir("roteiros") if f.endswith('.json')]
    
    if not roteiros_disponiveis:
        st.warning("Nenhum roteiro encontrado. Vá na primeira aba e gere um roteiro primeiro!")
    else:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            api_deepgram = st.text_input("Deepgram API Key", type="password")
            roteiro_selecionado = st.selectbox("Selecione o Roteiro", roteiros_disponiveis)
        with col2:
            estilo_animacao = st.selectbox("Animação", ["Zoom In Suave", "Zoom Out Suave", "Nenhuma"])
        with col3:
            estilo_transicao = st.selectbox("Transição", ["Crossfade (Suave)", "Corte Seco"])

        if st.button("🎬 Gerar Locução e Vídeo Final", type="primary", use_container_width=True):
            if api_deepgram:
                caminho_roteiro = os.path.join("roteiros", roteiro_selecionado)
                with open(caminho_roteiro, "r", encoding="utf-8") as f:
                    dados_roteiro = json.load(f)
                
                texto_narracao = dados_roteiro.get("texto", "")
                
                if texto_narracao:
                    audio_path = f"temp_audio_{roteiro_selecionado.replace('.json', '.mp3')}"
                    
                    with st.spinner("🎙️ Clonando voz..."):
                        caminho_gerado, erro_audio = gerar_audio_fishaudio(texto_narracao, audio_path, API_FISH, VOZ_MATHEUS)
                    
                    if not erro_audio:
                        st.success("✅ Áudio gerado!")
                        with st.spinner("⏱️ Mapeando os tempos..."):
                            palavras = obter_timestamps_deepgram(caminho_gerado, api_deepgram)
                        
                        if palavras:
                            nome_video = f"video_{roteiro_selecionado.replace('.json', '.mp4')}"
                            
                            # Passa os seletores escolhidos na UI para o gerador
                            output_file = gerar_video(
                                caminho_audio=caminho_gerado, 
                                palavras_deepgram=palavras, 
                                pasta_base=pasta_base, 
                                animacao=estilo_animacao, 
                                transicao=estilo_transicao, 
                                output_name=nome_video
                            )
                            
                            if output_file:
                                st.success("🎉 Vídeo finalizado!")
                                st.video(output_file)
                                
                        if os.path.exists(caminho_gerado):
                            os.remove(caminho_gerado)
                    else:
                        st.error(erro_audio)
            else:
                st.warning("Por favor, insira a chave da API do Deepgram.")

# ==========================================
# ABA 3: GERENCIADOR DE ARQUIVOS (VER E COLAR)
# ==========================================
with tab3:
    pastas = [d for d in os.listdir(pasta_base) if os.path.isdir(os.path.join(pasta_base, d))]
    
    if pastas:
        col_selecao, col_vazia = st.columns([1, 2])
        with col_selecao:
            pasta_selecionada = st.selectbox("Selecione o golpe/termo para gerenciar:", sorted(pastas))
            
        caminho_pasta = os.path.join(pasta_base, pasta_selecionada)
        st.divider()
        
        col_upload, col_galeria = st.columns([1, 2])
        
        with col_upload:
            st.subheader("Adicionar Mídia")
            if st.button("📋 Colar Imagem Copiada", use_container_width=True):
                try:
                    imagem = ImageGrab.grabclipboard()
                    if isinstance(imagem, Image.Image):
                        nome_arquivo = f"img_{int(time.time())}.png"
                        imagem.save(os.path.join(caminho_pasta, nome_arquivo))
                        st.success(f"Imagem salva!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Nenhuma imagem na área de transferência.")
                except Exception as e:
                    st.error(f"Erro ao colar: {e}")
            
            st.write("---")
            uploaded_file = st.file_uploader("Upload normal de mídias", type=['png', 'jpg', 'jpeg', 'mp4', 'mov'])
            if uploaded_file is not None:
                with open(os.path.join(caminho_pasta, uploaded_file.name), "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success("Salvo com sucesso!")
                time.sleep(1)
                st.rerun()

        with col_galeria:
            st.subheader("Arquivos na pasta")
            arquivos = os.listdir(caminho_pasta)
            if arquivos:
                cols = st.columns(3)
                for i, arquivo in enumerate(arquivos):
                    with cols[i % 3]:
                        caminho_arquivo = os.path.join(caminho_pasta, arquivo)
                        if arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                            st.image(caminho_arquivo, use_container_width=True)
                        else:
                            st.video(caminho_arquivo)
                        if st.button("🗑️", key=f"del_{arquivo}", help=f"Deletar {arquivo}"):
                            os.remove(caminho_arquivo)
                            st.rerun()
            else:
                st.info("Esta pasta ainda está vazia.")
    else:
        st.warning("Nenhuma pasta encontrada. Crie as pastas no terminal primeiro!")