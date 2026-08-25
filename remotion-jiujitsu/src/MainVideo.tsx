import { AbsoluteFill, Audio, useCurrentFrame, useVideoConfig, spring, staticFile } from "remotion";
import { CenaClip } from "./CenaClip";
import React from "react";

export const MainVideo: React.FC<any> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const tempoAtual = frame / fps;
  let palavraAtual = "";
  let frameInicioPalavra = 0;

  if (props.palavras) {
    const encontrada = props.palavras.find(
      (p: any) => tempoAtual >= p.start && tempoAtual <= (p.end || p.start + 0.6)
    );
    if (encontrada) {
      palavraAtual = encontrada.word;
      frameInicioPalavra = Math.floor(encontrada.start * fps);
    }
  }

  const scaleSpring = spring({
    fps,
    frame: frame - frameInicioPalavra,
    config: { damping: 12, stiffness: 200, mass: 0.5 },
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {props.cenas?.map((cena: any, index: number) => {
        const endFrame = cena.startFrame + cena.durationFrames;
        if (frame >= cena.startFrame && frame < endFrame) {
          return (
            <CenaClip
              key={index}
              // staticFile avisa o Remotion para ler o arquivo diretamente do HD sem empacotar
              file={staticFile(cena.file.replace('/assets/', 'assets/'))}
              type={cena.type}
              startFrame={cena.startFrame}
              durationFrames={cena.durationFrames}
              animacao={props.animacao}
              estiloVisual={props.estiloVisual}
            />
          );
        }
        return null;
      })}

      {/* AQUI ESTÁ A MÁGICA: staticFile resolve o caminho perfeitamente, ignorando a pasta Temp */}
      {props.audioUrl && <Audio src={staticFile(props.audioUrl.replace('/assets/', 'assets/'))} />}

      {palavraAtual && (
        <AbsoluteFill
          style={{
            justifyContent: "flex-end",
            alignItems: "center",
            paddingBottom: "140px",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              transform: `scale(${scaleSpring})`,
              backgroundColor: "rgba(0, 0, 0, 0.85)",
              padding: "14px 28px",
              borderRadius: "14px",
              border: "3px solid #FFD700",
              boxShadow: "0 10px 25px rgba(0,0,0,0.8)",
            }}
          >
            <span
              style={{
                fontFamily: "Arial, sans-serif",
                fontSize: "52px",
                fontWeight: "900",
                color: "#FFFFFF",
                textTransform: "uppercase",
                letterSpacing: "1px",
                textShadow: "3px 3px 0px #000000",
              }}
            >
              {palavraAtual}
            </span>
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};