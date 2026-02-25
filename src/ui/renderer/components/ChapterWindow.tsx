import React, { useState } from 'react';
import { StoryConfig, ChapterData } from '../../shared/types';
import DialogBar from './DialogBar';

interface ChapterWindowProps {
  config: StoryConfig;
}

const ChapterWindow: React.FC<ChapterWindowProps> = ({ config }) => {
  const [chapter, setChapter] = useState<ChapterData>({
    fileName: 'chapter-1.xml',
    chapterName: 'The Awakening',
    dialogs: [
      { id: '1', characterName: 'narrator', content: 'The city was quiet.', attributes: { emotion: 'calm' } },
      { id: '2', characterName: 'Hendrix', content: 'We need to move, now.', attributes: { volume: 'loud', speed: 'fast' } }
    ]
  });

  const handleSave = async () => {
    // 1. Serialize UI state to XML via Backend utility
    // 2. Call IPC to save file
    // 3. Run validation script on saved file
    console.log('Saving chapter to story-xml...', chapter);
    // Mock validation
    const success = true; 
    if (!success) {
      alert("Validation failed after save");
    }
  };

  return (
    <div className="chapter-window">
      <header className="chapter-header">
        <h1>Chapter Name: [{chapter.chapterName}]</h1>
        <div className="character-stats">
          <span>Characters [{new Set(chapter.dialogs.map(d => d.characterName)).size}]</span>
          <select>
            {Array.from(new Set(chapter.dialogs.map(d => d.characterName))).map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>
        <div className="dialog-stats">
          <span>Dialogs [{chapter.dialogs.length}]</span>
        </div>
        <button onClick={handleSave}>Save XML</button>
      </header>
      
      <main className="chapter-body">
        {chapter.dialogs.map((dialog) => (
          <DialogBar key={dialog.id} dialog={dialog} config={config} />
        ))}
      </main>
    </div>
  );
};

export default ChapterWindow;
