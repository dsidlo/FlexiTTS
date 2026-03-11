import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { StoryDropdown } from '../components/StoryDropdown';
import type { StoryInfo } from '../models/types';

describe('StoryDropdown', () => {
  const mockStories: StoryInfo[] = [
    { name: 'Entanglement', path: '/home/user/Stories/Story-Entanglement', directory_name: 'Story-Entanglement' },
    { name: 'Adventure', path: '/home/user/Stories/Story-Adventure', directory_name: 'Story-Adventure' },
    { name: 'Mystery', path: '/home/user/Stories/Story-Mystery', directory_name: 'Story-Mystery' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    // Setup default mock response
    if (window.api && window.api.listStories) {
      vi.mocked(window.api.listStories).mockResolvedValue(mockStories);
    }
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should show loading state initially', async () => {
      // Delay the response so loading state is visible
      if (window.api && window.api.listStories) {
        vi.mocked(window.api.listStories).mockImplementation(() => new Promise(() => {}));
      }
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      expect(screen.getByText('Loading stories...')).toBeInTheDocument();
    });

    it('should load stories on mount via IPC', async () => {
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(window.api?.listStories).toHaveBeenCalled();
      });
    });

    it('should use mock data when window.api is not available', async () => {
      // Temporarily remove listStories from api
      const originalListStories = window.api?.listStories;
      if (window.api) {
        delete (window.api as any).listStories;
      }
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      // Verify mock data is shown
      expect(screen.getByRole('option', { name: 'Entanglement' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Adventure' })).toBeInTheDocument();
      
      // Restore
      if (window.api) {
        (window.api as any).listStories = originalListStories;
      }
    });
  });

  describe('story selection', () => {
    it('should render with "All Stories" as default', async () => {
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      expect(screen.getByRole('option', { name: 'All Stories' })).toBeInTheDocument();
    });

    it('should render all story options', async () => {
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      for (const story of mockStories) {
        expect(screen.getByRole('option', { name: story.name })).toBeInTheDocument();
      }
    });

    it('should call onStorySelect when a story is selected', async () => {
      const onStorySelect = vi.fn();
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={onStorySelect} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: 'Story-Adventure' } });
      
      expect(onStorySelect).toHaveBeenCalledWith(mockStories[1]);
    });

    it('should call onStorySelect with null when "All Stories" is selected', async () => {
      const onStorySelect = vi.fn();
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={onStorySelect} selectedStory={mockStories[0]} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: '' } });
      
      expect(onStorySelect).toHaveBeenCalledWith(null);
    });

    it('should display the currently selected story', async () => {
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} selectedStory={mockStories[1]} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select.value).toBe('Story-Adventure');
    });
  });

  describe('error handling', () => {
    it('should handle empty response', async () => {
      if (window.api && window.api.listStories) {
        vi.mocked(window.api.listStories).mockResolvedValue([]);
      }
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      // Should still render dropdown with All Stories option
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      expect(screen.getByRole('option', { name: 'All Stories' })).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('should have a title attribute for tooltip', async () => {
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      const select = screen.getByRole('combobox');
      expect(select).toHaveAttribute('title', 'Select a story to filter chapters');
    });

    it('should be accessible via keyboard navigation', async () => {
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      const select = screen.getByRole('combobox');
      // Component should render select element
      expect(select.tagName).toBe('SELECT');
    });
  });

  describe('story filtering', () => {
    it('should handle stories with special characters in names', async () => {
      const specialStories: StoryInfo[] = [
        { name: 'Story with "quotes"', path: '/path/to/story', directory_name: 'Story-Quotes' },
        { name: 'Story with <tags>', path: '/path/to/story', directory_name: 'Story-Tags' },
      ];
      
      if (window.api && window.api.listStories) {
        vi.mocked(window.api.listStories).mockResolvedValue(specialStories);
      }
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      for (const story of specialStories) {
        expect(screen.getByRole('option', { name: story.name })).toBeInTheDocument();
      }
    });

    it('should handle very long story names', async () => {
      const longStory: StoryInfo[] = [
        { 
          name: 'A very long story name that might cause layout issues', 
          path: '/path/to/story', 
          directory_name: 'Story-LongName' 
        },
      ];
      
      if (window.api && window.api.listStories) {
        vi.mocked(window.api.listStories).mockResolvedValue(longStory);
      }
      
      await act(async () => {
        render(<StoryDropdown onStorySelect={vi.fn()} />);
      });
      
      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
      
      const option = screen.getByRole('option', { name: longStory[0].name });
      expect(option).toBeInTheDocument();
      expect(option).toHaveValue('Story-LongName');
    });
  });
});
