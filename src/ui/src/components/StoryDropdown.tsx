import React, { useState, useEffect } from 'react';
import type { StoryInfo } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';

interface StoryDropdownProps {
  onStorySelect: (story: StoryInfo | null) => void;
  selectedStory?: StoryInfo | null;
}

export const StoryDropdown: React.FC<StoryDropdownProps> = ({ 
  onStorySelect, 
  selectedStory 
}) => {
  const [stories, setStories] = useState<StoryInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStories();
  }, []);

  const loadStories = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Use PythonBridgeService to get available stories via IPC
      if (window.api?.listStories) {
        try {
          const storiesData = await PythonBridgeService.listStories();
          setStories(storiesData || []);
        } catch (e) {
          console.error('Error calling listStories:', e);
          setStories([]);
        }
      } else {
        // Mock data for development
        const mockStories: StoryInfo[] = [
          { name: 'Entanglement', path: '/home/user/Stories/Story-Entanglement', directory_name: 'Story-Entanglement' },
          { name: 'Adventure', path: '/home/user/Stories/Story-Adventure', directory_name: 'Story-Adventure' }
        ];
        setStories(mockStories);
      }
    } catch (err) {
      console.error('Error loading stories:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleStoryChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedValue = event.target.value;
    
    if (selectedValue === '') {
      onStorySelect(null);
    } else {
      const story = stories.find(s => s.directory_name === selectedValue);
      onStorySelect(story || null);
    }
  };

  if (loading) {
    return (
      <div style={{ 
        padding: '8px 12px', 
        background: '#f5f5f5', 
        border: '1px solid #ddd',
        borderRadius: '4px',
        color: '#666'
      }}>
        Loading stories...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ 
        padding: '8px 12px', 
        background: '#ffeaa7', 
        border: '1px solid #fdcb6e',
        borderRadius: '4px',
        color: '#e17055'
      }}>
        Error: {error}
      </div>
    );
  }

  return (
    <select
      value={selectedStory?.directory_name || ''}
      onChange={handleStoryChange}
      style={{
        padding: '8px 12px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        background: '#ffffff',
        color: '#333',
        fontSize: '14px',
        minWidth: '150px',
        cursor: 'pointer'
      }}
      title="Select a story to filter chapters"
    >
      <option value="">All Stories</option>
      {(stories || []).map(story => (
        <option key={story.directory_name} value={story.directory_name}>
          {story.name}
        </option>
      ))}
    </select>
  );
};

export default StoryDropdown;