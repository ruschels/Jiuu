import { AbsoluteFill, Img, OffthreadVideo, interpolate, useCurrentFrame } from "remotion";
import React from "react";

export const CenaClip: React.FC<any> = ({
  file,
  type,
  startFrame,
  durationFrames,
  animacao,
  estiloVisual,
}) => {
  const frame = useCurrentFrame();
  const relativeFrame = frame - startFrame;

  if (relativeFrame < 0 || relativeFrame >= durationFrames) {
    return null;
  }

  // Lógica de Animação de Zoom (incluindo o novo Ken Burns)
  let scale = 1;
  if (animacao === "Zoom In Suave" || animacao === "Ken Burns") {
    scale = interpolate(relativeFrame, [0, durationFrames], [1, 1.15], {
      extrapolateRight: "clamp",
    });
  } else if (animacao === "Zoom Out Suave") {
    scale = interpolate(relativeFrame, [0, durationFrames], [1.15, 1], {
      extrapolateRight: "clamp",
    });
  }

  // Estilos Visuais Diferentes
  let containerStyle: React.CSSProperties = {
    position: "absolute",
    width: "100%",
    height: "100%",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
  };

  if (estiloVisual === "Minimalista (Clean)") {
    containerStyle.backgroundColor = "#111";
  } else if (estiloVisual === "Card Cyberpunk") {
    containerStyle.border = "8px solid #FFD700";
    containerStyle.backgroundColor = "#0b0b0b";
  }

  return (
    <AbsoluteFill style={containerStyle}>
      {/* Fundo Desfocado automático para o estilo Moderno */}
      {estiloVisual === "Moderno (Blur Fundo)" && type === "image" && (
        <div
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            backgroundImage: `url(${file})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            filter: "blur(25px) brightness(0.6)",
            transform: "scale(1.2)",
          }}
        />
      )}

      {/* Mídia Principal */}
      <div style={{ transform: `scale(${scale})`, width: "100%", height: "100%", display: "flex", justifyContent: "center", alignItems: "center" }}>
        {type === "video" ? (
          <OffthreadVideo
            src={file}
            style={{
              width: "100%",
              height: "100%",
              objectFit: estiloVisual === "Minimalista (Clean)" ? "contain" : "cover",
            }}
          />
        ) : (
          <Img
            src={file}
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: estiloVisual === "Minimalista (Clean)" ? "contain" : "cover",
              boxShadow: estiloVisual === "Card Cyberpunk" ? "0 0 30px rgba(255,215,0,0.5)" : "none",
            }}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};