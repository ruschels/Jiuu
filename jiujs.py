import streamlit as st
import os
import random
import unicodedata
import requests
import time
import json
import re
import subprocess
import shutil
from PIL import Image, ImageGrab
from google import genai
from google.genai import types

# ==========================================
# CONFIGURAÇÕES
# ==========================================
MODELO_GEMINI = "gemini-flash-latest" 
VOZ_PADRAO = "8a7a95ba239d4475afcad5dbebb24a48" # ID da voz (Pode ir para o GitHub, não é uma chave de segurança)

# ==========================================
# INICIALIZAÇÃO DE ESTADO
# ==========================================
if 'preparo_concluido' not in st.session_state:
    st.session_state.preparo_concluido = False
if 'nome_video_atual' not in st.session_state:
    st.session_state.nome_video_atual = ""

# ==========================================
# FUNÇÕES DE LÓGICA E IA
# ==========================================
def chamar_gemini_com_retry(prompt, api_key, max_tentativas_por_modelo=3, delay_segundos=4):
    modelos_fallback = [MODELO_GEMINI, "gemini-3.6-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"]
    client = genai.Client(api_key=api_key)
    log_container = st.empty()
    
    for modelo in modelos_fallback:
        for tentativa in range(max_tentativas_por_modelo):
            log_container.info(f"🔄 Tentando conectar ao modelo: **{modelo}**...")
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                log_container.success(f"✅ Sucesso! O modelo **{modelo}** processou.")
                time.sleep(1)
                log_container.empty() 
                return response.text
            except Exception as e:
                erro_str = str(e)
                if "503" in erro_str or "429" in erro_str:
                    log_container.warning(f"⚠️ **{modelo}** sobrecarregado. Aguardando...")
                    if tentativa < max_tentativas_por_modelo - 1:
                        time.sleep(delay_segundos)
                        continue
                    else: break 
                else:
                    log_container.error(f"❌ Erro no **{modelo}**... Pulando.")
                    time.sleep(2) 
                    break 
    raise Exception(f"Falha de conexão em todas as rotas. Tente novamente.")

def gerar_audio_fishaudio(texto, output_path, api_key, voice_id):
    url = "https://api.fish.audio/v1/tts"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"text": texto, "reference_id": voice_id, "format": "mp3"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            with open(output_path, "wb") as f: f.write(response.content)
            return output_path, None
        return None, f"Status {response.status_code}: {response.text}"
    except Exception as e: return None, f"Erro de Conexão: {str(e)}"

def normalizar_texto(texto):
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8').lower().strip()

def obter_timestamps_deepgram(caminho_audio, api_key):
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=pt-BR&punctuate=true"
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "audio/mpeg"}
    with open(caminho_audio, "rb") as audio:
        response = requests.post(url, headers=headers, data=audio)
    if response.status_code == 200:
        return response.json()['results']['channels'][0]['alternatives'][0]['words']
    st.error(f"Erro no Deepgram: {response.text}")
    return []

# ==========================================
# RENDERIZAÇÃO REMOTION (ETAPA 1: PREPARAÇÃO LIMPA)
# ==========================================
def preparar_assets_remotion(caminho_audio_temp, palavras_deepgram, pasta_base, animacao, transicao, estilo_visual):
    pastas_disponiveis = [d for d in os.listdir(pasta_base) if os.path.isdir(os.path.join(pasta_base, d))]
    mapa_pastas = {normalizar_texto(p): p for p in pastas_disponiveis}
    
    fps = 30
    timeline = []
    
    # Limpa a pasta e garante que ela existe
    assets_dir = os.path.join("remotion-jiujitsu", "public", "assets")
    if os.path.exists(assets_dir):
        shutil.rmtree(assets_dir, ignore_errors=True)
    os.makedirs(assets_dir, exist_ok=True)
    
    for item in palavras_deepgram:
        palavra_limpa = normalizar_texto(item['word'])
        if palavra_limpa in mapa_pastas:
            caminho_pasta = os.path.join(pasta_base, mapa_pastas[palavra_limpa])
            arquivos = [f for f in os.listdir(caminho_pasta) if f.endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov'))]
            if arquivos:
                media_escolhida = random.choice(arquivos)
                nome_unico = f"{palavra_limpa}_{len(timeline)}_{media_escolhida}"
                destino_media = os.path.join(assets_dir, nome_unico)
                shutil.copy(os.path.join(caminho_pasta, media_escolhida), destino_media)
                
                timeline.append({
                    "keyword": palavra_limpa, 
                    "startTime": item['start'], 
                    "endTime": item.get('end', item['start'] + 1.0),
                    "file": f"assets/{nome_unico}",
                    "type": "video" if media_escolhida.endswith(('.mp4', '.mov')) else "image"
                })

    if not timeline:
        st.error("❌ Nenhuma palavra correspondeu às pastas de mídia!")
        return False

    # Copia o áudio final
    destino_audio = os.path.join(assets_dir, "audio_final.mp3")
    shutil.copy(caminho_audio_temp, destino_audio)

    dados_remotion = {
        "audioUrl": "assets/audio_final.mp3",
        "fps": fps,
        "animacao": animacao,
        "transicao": transicao,
        "estiloVisual": estilo_visual,
        "palavras": palavras_deepgram,
        "cenas": []
    }

    for i, cena in enumerate(timeline):
        start_time = cena['startTime']
        end_time = timeline[i+1]['startTime'] if i + 1 < len(timeline) else cena['endTime']
        
        overlap = 0.3 if transicao == "Crossfade (Suave)" and i > 0 else 0
        start_time_ajustado = max(0, start_time - overlap)
        duracao = max(0.5, (end_time - start_time) + overlap)

        dados_remotion["cenas"].append({
            "startFrame": int(start_time_ajustado * fps),
            "durationFrames": int(duracao * fps),
            "file": cena['file'],
            "type": cena['type'],
            "overlapFrames": int(overlap * fps)
        })

    caminho_json = os.path.join("remotion-jiujitsu", "public", "timeline.json")
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(dados_remotion, f, indent=4, ensure_ascii=False)
            
    return True

# ==========================================
# RENDERIZAÇÃO REMOTION (ETAPA 2: RENDERIZAR)
# ==========================================
def executar_render_remotion(output_name):
    with st.spinner('🎬 Renderizando vídeo no Remotion... Acompanhe o log abaixo:'):
        node_dir = r"C:\Users\matheus.souza_prf\Desktop\node-novo"
        env_blindado = os.environ.copy()
        env_blindado["PATH"] = node_dir + os.pathsep + env_blindado.get("PATH", "")
        comando = f"npx.cmd remotion render Main ../{output_name} --props=public/timeline.json"
        
        log_container = st.empty()
        log_container.code(f"Iniciando renderização limpa...\nComando: {comando}\n", language="bash")
        
        try:
            processo = subprocess.Popen(
                comando,
                cwd="remotion-jiujitsu",
                env=env_blindado,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            log_text = ""
            for linha in processo.stdout:
                log_text += linha
                log_container.code(log_text, language="bash")
                
            processo.wait()
            if processo.returncode != 0: return None
        except Exception as e:
            st.error(f"❌ Erro ao abrir terminal: {str(e)}")
            return None

    if os.path.exists(output_name): return output_name
    return None

pasta_base = "imagens_jiu"
if not os.path.exists(pasta_base): os.makedirs(pasta_base)
if not os.path.exists("roteiros"): os.makedirs("roteiros")

# ==========================================
# INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="App de Jiu-Jitsu Studio", layout="wide")
st.title("🥋 App de Jiu-Jitsu Studio")
tab1, tab2, tab3 = st.tabs(["📝 Geração de Roteiro", "🎬 Gerador de Vídeo", "📁 Gerenciador de Pastas"])

with tab1:
    st.header("Gerar Roteiro com IA (Gemini)")
    st.write("A IA vai criar um roteiro fluido usando exclusivamente os termos das pastas que você já tem no sistema.")
    col_ai1, col_ai2 = st.columns(2)
    with col_ai1:
        api_gemini = st.text_input("API Key do Gemini", type="password", placeholder="Cole sua chave aqui...")
        tema_video = st.text_input("Tema do vídeo", placeholder="Ex: Combinações da guarda")
    with col_ai2:
        pastas_atuais = [d for d in os.listdir(pasta_base) if os.path.isdir(os.path.join(pasta_base, d))]
        st.write("📦 **Termos disponíveis:**")
        st.caption(", ".join(pastas_atuais) if pastas_atuais else "Nenhuma pasta.")

    if st.button("✨ Gerar Estrutura", type="primary"):
        if not api_gemini or not pastas_atuais or not tema_video:
            st.warning("Preencha todos os campos (incluindo a API Key) e garanta que existam pastas.")
        else:
            with st.spinner("Criando roteiro..."):
                prompt = f"""
                Especialista em Jiu-Jitsu para TikTok. Tema: '{tema_video}'.
                Obrigatório incluir naturalmente: {", ".join(pastas_atuais)}.
                Retorne apenas JSON estrito com "titulo", "texto" e "palavras_chave".
                """
                try:
                    roteiro_texto = chamar_gemini_com_retry(prompt, api_gemini)
                    if roteiro_texto.startswith("```json"): roteiro_texto = roteiro_texto[7:-3]
                    elif roteiro_texto.startswith("```"): roteiro_texto = roteiro_texto[3:-3]
                    json_roteiro = json.loads(roteiro_texto)
                    nome_limpo = re.sub(r'[^\w\-]', '_', tema_video).lower()
                    cam_salvar = os.path.join("roteiros", f"roteiro_{nome_limpo}.json")
                    with open(cam_salvar, "w", encoding="utf-8") as f: json.dump(json_roteiro, f, indent=4)
                    st.success("Salvo com sucesso!"); st.json(json_roteiro)
                except Exception as e: st.error(f"Erro: {e}")

with tab2:
    st.header("Sincronizar Áudio e Gerar Vídeo")
    roteiros_disponiveis = [f for f in os.listdir("roteiros") if f.endswith('.json')]
    
    if not roteiros_disponiveis:
        st.warning("Gere um roteiro primeiro!")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            api_deepgram = st.text_input("Deepgram API Key", type="password", placeholder="Cole sua chave aqui...")
            api_fish = st.text_input("Fish Audio API Key", type="password", placeholder="Cole sua chave aqui...")
            roteiro_selecionado = st.selectbox("Roteiro", roteiros_disponiveis)
        with col2: estilo_visual = st.selectbox("Estilo Visual", ["Moderno (Blur Fundo)", "Minimalista (Clean)", "Card Cyberpunk"])
        with col3: estilo_animacao = st.selectbox("Animação", ["Zoom In Suave", "Zoom Out Suave", "Ken Burns", "Nenhuma"])
        with col4: estilo_transicao = st.selectbox("Transição", ["Crossfade (Suave)", "Corte Seco"])

        st.divider()
        st.write("### Controle de Renderização")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🎙️ Passo 1: Preparar Áudio", type="primary", use_container_width=True):
                if api_deepgram and api_fish:
                    caminho_roteiro = os.path.join("roteiros", roteiro_selecionado)
                    with open(caminho_roteiro, "r", encoding="utf-8") as f: dados_roteiro = json.load(f)
                    texto_narracao = dados_roteiro.get("texto", "")
                    
                    if texto_narracao:
                        audio_path = f"temp_audio.mp3"
                        with st.spinner("Clonando voz..."):
                            caminho_gerado, erro_audio = gerar_audio_fishaudio(texto_narracao, audio_path, api_fish, VOZ_PADRAO)
                        
                        if not erro_audio:
                            st.success("Áudio gerado!")
                            with st.spinner("Mapeando tempos..."):
                                palavras = obter_timestamps_deepgram(caminho_gerado, api_deepgram)
                            if palavras:
                                with st.spinner("Construindo assets..."):
                                    sucesso = preparar_assets_remotion(caminho_gerado, palavras, pasta_base, estilo_animacao, estilo_transicao, estilo_visual)
                                if sucesso:
                                    st.session_state.preparo_concluido = True
                                    st.session_state.nome_video_atual = f"video_{roteiro_selecionado.replace('.json', '.mp4')}"
                                    st.success("Tudo pronto! Clique em Renderizar.")
                            if os.path.exists(caminho_gerado): os.remove(caminho_gerado)
                        else: st.error(erro_audio)
                else: st.warning("Insira as chaves do Deepgram e do Fish Audio para prosseguir.")
                    
        with col_btn2:
            if st.button("🎬 Passo 2: Renderizar Vídeo", type="primary", disabled=not st.session_state.preparo_concluido, use_container_width=True):
                if st.session_state.nome_video_atual:
                    output_file = executar_render_remotion(st.session_state.nome_video_atual)
                    if output_file:
                        st.success("Vídeo finalizado!")
                        st.video(output_file)
                        st.session_state.preparo_concluido = False 
                    else: st.error("O Remotion falhou. Verifique o log.")

with tab3:
    pastas = [d for d in os.listdir(pasta_base) if os.path.isdir(os.path.join(pasta_base, d))]
    if pastas:
        col_selecao, col_vazia = st.columns([1, 2])
        with col_selecao: pasta_selecionada = st.selectbox("Gerenciar:", sorted(pastas))
        caminho_pasta = os.path.join(pasta_base, pasta_selecionada)
        st.divider()
        col_upload, col_galeria = st.columns([1, 2])
        with col_upload:
            if st.button("📋 Colar Imagem", use_container_width=True):
                try:
                    imagem = ImageGrab.grabclipboard()
                    if isinstance(imagem, Image.Image):
                        imagem.save(os.path.join(caminho_pasta, f"img_{int(time.time())}.png"))
                        st.rerun()
                except: st.error("Erro ao colar imagem")
            uploaded_file = st.file_uploader("Ou envie arquivo", type=["png", "jpg", "jpeg", "mp4", "mov"])
            if uploaded_file:
                with open(os.path.join(caminho_pasta, uploaded_file.name), "wb") as f: f.write(uploaded_file.getbuffer())
                st.rerun()
        with col_galeria:
            arquivos = [f for f in os.listdir(caminho_pasta) if f.endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov'))]
            if arquivos:
                cols_galeria = st.columns(3)
                for idx, arq in enumerate(arquivos):
                    caminho_arq = os.path.join(caminho_pasta, arq)
                    with cols_galeria[idx % 3]:
                        if arq.endswith(('.png', '.jpg', '.jpeg')): st.image(caminho_arq, use_container_width=True)
                        else: st.video(caminho_arq)
                        if st.button("🗑️", key=f"del_{pasta_selecionada}_{arq}"):
                            os.remove(caminho_arq)
                            st.rerun()