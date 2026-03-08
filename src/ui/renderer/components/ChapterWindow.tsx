import React, { useState, useEffect } from 'react';
import { StoryConfig, ChapterData, StoryInfo } from '../../shared/types';
import { PythonBridgeService } from '../../src/services/pythonBridge';
import DialogBar from './DialogBar';

interface ChapterWindowProps {
  config: StoryConfig;
}

const ChapterWindow: React.FC<ChapterWindowProps> = ({ config }) => {
  const [chapter, setChapter] = useState<ChapterData>({
    fileName: 'chapter-1.xml',
    chapterName: 'The Awakening',
    dialogs: [
      { id: '1', character: 'narrator', text: 'The city was quiet.', attributes: { emotion: 'calm' } },
      { id: '2', character: 'Hendrix', text: 'We need to move, now.', attributes: { volume: 'loud', speed: 'fast' } }
    ]
  });

  // Story selection state
  const [stories, setStories] = useState<StoryInfo[]>([]);
  const [selectedStory, setSelectedStory] = useState<StoryInfo | null>(null);
  const [currentConfig, setCurrentConfig] = useState<StoryConfig>(config);
  const [loadingStories, setLoadingStories] = useState(false);
  const [storyError, setStoryError] = useState<string | null>(null);

  // Fetch stories on component mount
  useEffect(() => {
    fetchStories();
  }, []);

  /**
   * Fetch available stories from the backend
   */
  const fetchStories = async () => {
    setLoadingStories(true);
    setStoryError(null);
    
    try {
      const storyList = await PythonBridgeService.listStories();
      setStories(storyList);
      
      // If no story is selected and we have stories, select the first one
      if (!selectedStory && storyList.length > 0) {
        await handleStoryChange(storyList[0]);
      }
    } catch (error) {
      console.error('Failed to fetch stories:', error);
      setStoryError(error instanceof Error ? error.message : 'Failed to load stories');
    } finally {
      setLoadingStories(false);
    }
  };

  /**
   * Handle story selection change
   * Reloads the story configuration when a different story is selected
   */
  const handleStoryChange = async (story: StoryInfo | null) => {
    if (!story) {
      setSelectedStory(null);
      return;
    }

    setSelectedStory(story);
    
    try {
      // Load the story-specific configuration
      const storyConfig = await PythonBridgeService.loadStoryConfigForStory(story.directory_name);
      setCurrentConfig(storyConfig);
      
      // Set this as the current story in the backend
      await PythonBridgeService.setCurrentStory(story.directory_name);
      
      console.log(`Loaded config for story: ${story.name}`, storyConfig);
    } catch (error) {
      console.error(`Failed to load config for story ${story.name}:`, error);
      setStoryError(`Failed to load config for ${story.name}`);
    }
  };

  /**
   * Handle dropdown selection change
   */
  const handleSelectChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedDirectory = event.target.value;
    const story = stories.find(s => s.directory_name === selectedDirectory);
    handleStoryChange(story || null);
  };

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
        <div className="header-left">
          <h1>Chapter Name: [{chapter.chapterName}]</h1>
          
          {/* Story Selection Dropdown */}
          <div className="story-selector">
            <label htmlFor="story-select">Story:</label>
            <select
              id="story-select"
              value={selectedStory?.directory_name || ''}
              onChange={handleSelectChange}
              disabled={loadingStories}
              className="story-dropdown"
            >
              <option value="">
                {loadingStories ? 'Loading...' : 'Select a story...'}
              </option>
              {stories.map((story) => (
                <option key={story.directory_name} value={story.directory_name}>
                  {story.name}
                </option>
              ))}
            </select>
            {storyError && <span className="story-error" title={storyError}>⚠️</span>}
          </div>
        </div>

        <div className="header-right">
          <div className="character-stats">
            <span>Characters [{new Set(chapter.dialogs.map(d => d.character)).size}]</span>
            <select>
              {Array.from(new Set(chapter.dialogs.map(d => d.character))).map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
          <div className="dialog-stats">
            <span>Dialogs [{chapter.dialogs.length}]</span>
          </div>
          <button onClick={handleSave}>Save XML</button>
        </div>
      </header>
      
      <main className="chapter-body">
        {chapter.dialogs.map((dialog) => (
          <DialogBar 
            key={dialog.id} 
            dialog={{
              ...dialog,
              characterName: dialog.character,
              content: dialog.text
            }} 
            config={currentConfig} 
          />
        ))}
      </main>
    </div>
  );
};

export default ChapterWindow;