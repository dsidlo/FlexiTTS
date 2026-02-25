import React, { useState } from 'react';
import { DialogSection, StoryConfig } from '../../shared/types';

interface DialogBarProps {
  dialog: DialogSection;
  config: StoryConfig;
}

const DialogBar: React.FC<DialogBarProps> = ({ dialog, config }) => {
  const [expanded, setExpanded] = useState(false);
  const [content, setContent] = useState(dialog.content);

  // Generate color based on character or default grey for narrator
  const isNarrator = dialog.characterName.toLowerCase() === 'narrator';
  const getCharacterColor = (name: string) => {
    if (name.toLowerCase() === 'narrator') return '#e0e0e0'; // Grey
    // Simple hash to generate a hex color from the character name string
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
  };
  const bgColor = getCharacterColor(dialog.characterName);

  return (
    <div 
      className="dialog-bar" 
      style={{ backgroundColor: bgColor, padding: '10px', margin: '5px 0', border: '1px solid #ccc' }}
      onClick={() => setExpanded(!expanded)}
      onContextMenu={(e) => {
        e.preventDefault();
        // Implement Context menu logic (Rich-Click)
        console.log('Context menu for attributes', dialog.attributes);
        alert('Rich-click mock: Show attributes ' + JSON.stringify(dialog.attributes));
      }}
    >
      <div className="dialog-header">
        <strong>{dialog.characterName}</strong>: {expanded ? '' : content.substring(0, 50) + '...'}
      </div>
      
      {expanded && (
        <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
          <textarea 
            value={content} 
            onChange={(e) => setContent(e.target.value)} 
            rows={4} 
            style={{ width: '100%', marginTop: '10px' }}
          />
        </div>
      )}
    </div>
  );
};

export default DialogBar;
