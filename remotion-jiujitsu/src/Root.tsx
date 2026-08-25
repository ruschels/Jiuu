import { Composition, getInputProps } from 'remotion';
import { MainVideo } from './MainVideo';
import React from 'react';

export const RemotionRoot: React.FC = () => {
  // Recebe os dados brutos enviados pelo Python
  const props = getInputProps() as any;

  // Calcula o tempo exato do vídeo para evitar tela preta no final
  let totalDuration = 30; // Segurança mínima
  if (props.cenas && props.cenas.length > 0) {
    const ultimaCena = props.cenas[props.cenas.length - 1];
    totalDuration = ultimaCena.startFrame + ultimaCena.durationFrames;
  }

  return (
    <>
      <Composition
        id="Main"
        component={MainVideo}
        durationInFrames={totalDuration}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={props}
      />
    </>
  );
};
// BUSTER_CACHE_REMOTION: 1787684228.6679487