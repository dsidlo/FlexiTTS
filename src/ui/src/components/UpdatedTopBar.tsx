import React, { useState, useCallback } from 'react';
import type { StoryConfig } from '../models/types';
import type { StoryInfo } from './extended-types';
import { StoryDropdown } from './StoryDropdown';

interface UpdatedTopBarProps {
  config?: StoryConfig;
  chapter: any;
  filePath: string;
  chapterList: string[];
  hasChapterAudio: boolean;
  selectedCharacter: string;
  selectedStory?: StoryInfo | null;
  onChapterSelect: (filePath: string, storyInfo?: StoryInfo) => void;
  onCharacterSelect: (character: string) => void;
  onStorySelect: (story: StoryInfo | null) => void;
  onSave: () => Promise<void>;
  onRenderComplete: () => void;
  hasUnsavedChanges: boolean;
  editorMode: boolean;
  onToggleEditor: () => void;
}

export const UpdatedTopBar: React.FC<UpdatedTopBarProps> = ({
  config,
  chapter,
  filePath,
  chapterList,
  hasChapterAudio,
  selectedCharacter,
  selectedStory,
  onChapterSelect,
  onCharacterSelect,
  onStorySelect,
  onSave,
  onRenderComplete,
  hasUnsavedChanges,
  editorMode,
  onToggleEditor
}) => {
  const [showChapterDropdown, setShowChapterDropdown] = useState(false);

  // Filter chapters based on selected story
  const getFilteredChapterList = useCallback(() => {
    if (!selectedStory) {
      return chapterList;
    }
    
    return chapterList.filter(chapter => 
      chapter.startsWith(selectedStory.directory_name + '/')
    );
  }, [chapterList, selectedStory]);

  const handleChapterSelect = (newFilePath: string) => {
    onChapterSelect(newFilePath, selectedStory);
    setShowChapterDropdown(false);
  };

  const handleStorySelect = (story: StoryInfo | null) => {
    onStorySelect(story);
    
    // If a story is selected, automatically switch to the first chapter in that story
    if (story) {
      const storyChapters = chapterList.filter(chapter => 
        chapter.startsWith(story.directory_name + '/')
      );
      
      if (storyChapters.length > 0) {
        onChapterSelect(storyChapters[0], story);
      }
    }
  };

  const currentChapterName = filePath.split('/').pop()?.replace(/\.(md|xml)$/, '') || 'Unknown Chapter';
  const currentStoryName = selectedStory?.name || 'Multiple Stories';
  const filteredChapters = getFilteredChapterList();

  return (
    <div className="top-bar" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '10px 20px',
      background: '#2c3e50',
      color: '#ecf0f1',
      borderBottom: '2px solid #34495e',
      minHeight: '60px',
      flexWrap: 'wrap',
      gap: '10px'
    }}>
      {/* Left section: Story and Chapter selection */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '15px', flex: 1 }}>
        {/* Story Dropdown */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '12px', color: '#bdc3c7', fontWeight: 'bold' }}>
            Story:
          </label>
          <StoryDropdown 
            onStorySelect={handleStorySelect} 
            selectedStory={selectedStory}
          />
        </div>

        {/* Chapter Selection */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', position: 'relative' }}>
          <label style={{ fontSize: '12px', color: '#bdc3c7', fontWeight: 'bold' }}>
            Chapter:
          </label>
          <button
            onClick={() => setShowChapterDropdown(!showChapterDropdown)}
            style={{
              padding: '8px 12px',
              background: selectedStory ? '#3498db' : '#7f8c8d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              minWidth: '200px',
              textAlign: 'left',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
            title={`${currentStoryName} - ${currentChapterName}`}
          >
            <span>{currentChapterName}</span>
            <span style={{ marginLeft: '8px' }}>▼</span>
          </button>

          {showChapterDropdown && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              background: 'white',
              border: '1px solid #bdc3c7',
              borderRadius: '4px',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
              zIndex: 1000,
              minWidth: '250px',
              maxHeight: '300px',
              overflowY: 'auto'
            }}>
              <div style={{ 
                padding: '8px 12px', 
                background: '#ecf0f1', 
                borderBottom: '1px solid #bdc3c7',
                fontWeight: 'bold',
                fontSize: '12px',
                color: '#2c3e50'
              }}>
                {selectedStory ? `${selectedStory.name} Chapters (${filteredChapters.length})` : `All Chapters (${filteredChapters.length})`}
              </div>
              {filteredChapters.map((chapterPath, idx) => {
                const chapterName = chapterPath.split('/').pop()?.replace(/\.(md|xml)$/, '') || chapterPath;
                const storyName = chapterPath.split('/')[0]?.replace('Story-', '') || '';
                const isSelected = chapterPath === filePath;
                
                return (
                  <button
                    key={idx}
                    onClick={() => handleChapterSelect(chapterPath)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      background: isSelected ? '#3498db' : 'transparent',
                      color: isSelected ? 'white' : '#2c3e50',
                      border: 'none',
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontSize: '14px',
                      borderBottom: '1px solid #ecf0f1'
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = '#ecf0f1';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 'bold' }}>{chapterName}</span>
                      {!selectedStory && <span style={{ fontSize: '12px', color: isSelected ? '#ecf0f1' : '#7f8c8d' }}>{storyName}</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Middle section: Character filter */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <label style={{ fontSize: '12px', color: '#bdc3c7', fontWeight: 'bold' }}>
          Filter:
        </label>
        <select
          value={selectedCharacter}
          onChange={(e) => onCharacterSelect(e.target.value)}
          style={{
            padding: '6px 10px',
            border: '1px solid #bdc3c7',
            borderRadius: '4px',
            background: '#ffffff',
            color: '#2c3e50',
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          <option value="">All Characters</option>
          {config?.characters?.map(char => (
            <option key={char.name} value={char.name}>{char.name}</option>
          ))}
        </select>
      </div>

      {/* Right section: Action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button
          onClick={onToggleEditor}
          style={{
            padding: '8px 16px',
            background: editorMode ? '#e74c3c' : '#2ecc71',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          {editorMode ? 'Close Editor' : 'Edit Markdown'}
        </button>

        <button
          onClick={onSave}
          disabled={!hasUnsavedChanges}
          style={{
            padding: '8px 16px',
            background: hasUnsavedChanges ? '#e67e22' : '#95a5a6',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: hasUnsavedChanges ? 'pointer' : 'not-allowed',
            fontSize: '14px',
            fontWeight: hasUnsavedChanges ? 'bold' : 'normal'
          }}
        >
          {hasUnsavedChanges ? 'Save Changes' : 'Saved'}
        </button>

        {hasChapterAudio && (
          <div style={{
            padding: '6px 12px',
            background: '#27ae60',
            color: 'white',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 'bold'
          }}>
            ♪ Has Audio
          </div>
        )}
      </div>

      {/* Click outside to close dropdown */}
      {showChapterDropdown && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 999
          }}
          onClick={() => setShowChapterDropdown(false)}
        />
      )}
    </div>
  );
};