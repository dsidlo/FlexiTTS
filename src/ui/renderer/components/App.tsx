import React, { useState, useEffect } from 'react';
import ChapterWindow from './ChapterWindow';
import { StoryConfig } from '../../shared/types';

// Mocked IPC for the renderer MVP
const mockIpc = {
  validateConfig: async () => ({ success: true }),
  validateChapterXml: async (path: string) => ({ success: true })
};

const App: React.FC = () => {
  const [config, setConfig] = useState<StoryConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initApp = async () => {
      // 1. Validate config via backend script
      const result = await mockIpc.validateConfig();
      if (!result.success) {
        setError(`Configuration Validation Error: ${result.error}`);
        return;
      }
      // 2. Load configuration (Mocked for MVP initialization)
      // In full implementation, this calls fs.readFileSync & js-yaml via IPC
      setConfig({
         global: { storyDir: './Story-Entanglement/', voices: 'refs/', chapters: 'story-chapters/', storyXml: 'story-xml/', logs: 'logs/', storyAudio: 'story-audio/', clips: 'story-audio/clips/', clipSeparation: 0.3 },
         llmXmlGenerator: [],
         dialogEffects: [],
         storyAudioPostProcess: {},
         characters: [{ name: 'narrator' }]
      });
    };
    initApp();
  }, []);

  if (error) {
    return <div className="error-modal"><h2>Error</h2><p>{error}</p></div>;
  }

  if (!config) {
    return <div>Loading FlexiTTS Configuration...</div>;
  }

  return (
    <div className="flexitts-app">
      <ChapterWindow config={config} />
    </div>
  );
};

export default App;
