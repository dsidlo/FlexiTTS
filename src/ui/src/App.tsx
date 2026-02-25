import { useState, useEffect } from 'react';
import './App.css';
import { PythonBridgeService } from './services/pythonBridge';
import type { StoryConfig, Chapter, DialogElement } from './models/types';
import { TopBar } from './components/TopBar';
import { DialogBar } from './components/DialogBar';

function App() {
  // We don't use config directly in rendering right now, but we validate and load it
  const [, setConfig] = useState<StoryConfig | null>(null);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [xmlContent, setXmlContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Context menu state
  const [showChapterMenu, setShowChapterMenu] = useState(false);
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });
  const [chapterList, setChapterList] = useState<string[]>([]);
  const [selectedCharacterFilter, setSelectedCharacterFilter] = useState<string>('');

  // In a real app this would come from the user's selection
  const [currentChapterFile, setCurrentChapterFile] = useState<string>('story/chapters/chapter1.xml');
  const [availableClips, setAvailableClips] = useState<string[]>([]);
  const [hasChapterAudio, setHasChapterAudio] = useState(false);
  const [isRenderCooldown, setIsRenderCooldown] = useState(false);

  useEffect(() => {
    const initApp = async () => {
      try {
        setLoading(true);
        
        // Load configuration
        await PythonBridgeService.validateConfig();
        const loadedConfig = await PythonBridgeService.loadStoryConfig();
        setConfig(loadedConfig);
        
        // Load chapter list first
        const fetchedList = await PythonBridgeService.listChapterFiles(loadedConfig.global['story-xml']);
        setChapterList(fetchedList);

        if (fetchedList.length > 0) {
           await loadChapter(fetchedList[0]);
        }
      } catch (err: unknown) {
        const error = err as Error;
        setError(error.message || 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    initApp();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadChapter = async (filePath: string) => {
    try {
      console.log(`Loading chapter: ${filePath}`);
      // Validate the XML
      try {
        await PythonBridgeService.validateChapterXML(filePath);
      } catch (validationErr: unknown) {
        console.warn('XML validation failed:', validationErr);
      }

      const loadedXml = await PythonBridgeService.readChapterFile(filePath);
      console.log(`Loaded XML for ${filePath}:`, loadedXml.substring(0, 50) + '...');
      
      const parsedChapter = parseChapterXML(loadedXml, filePath);
      console.log(`Parsed chapter:`, parsedChapter);
      setChapter(parsedChapter);
      setCurrentChapterFile(filePath);
      setSelectedCharacterFilter(''); // reset filter on load
      
      const chapterName = filePath.split('/').pop() || '';
      if (chapterName) {
         const clips = await PythonBridgeService.listChapterClips(chapterName);
         setAvailableClips(clips);
         const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
         setHasChapterAudio(hasAudio);
      }
      
      // Update xmlContent to reflect the parsed state so that save uses the properly formatted generator output
      setXmlContent(generateXMLFromChapter(parsedChapter));
    } catch (err) {
      console.error('Failed to load chapter:', err);
    }
  };

  const parseChapterXML = (xmlString: string, filePath: string): Chapter => {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlString, 'text/xml');
    
    // Check for parsing errors
    const parseError = xmlDoc.querySelector('parsererror');
    if (parseError) {
      console.error('Error parsing XML', parseError);
    }

    const chapterNode = xmlDoc.querySelector('chapter') || xmlDoc.querySelector('story');
    const chapterName = chapterNode?.getAttribute('name') || filePath.split('/').pop()?.replace('.xml', '') || 'Unknown Chapter';
    
    // Support either <dialog> or <narration> nodes depending on XML format
    // Also grab standard <dialog> nodes and <narration> nodes wherever they exist
    const dialogNodes = Array.from(xmlDoc.querySelectorAll('dialog, narration'));
    
    if (dialogNodes.length === 0) {
      console.warn("No <dialog> or <narration> nodes found in XML string: ", xmlString);
    }

    const dialogs: DialogElement[] = dialogNodes.map((node, index) => {
      const attributes: Record<string, string> = {};
      
      // Extract all attributes from the XML node
      for (let i = 0; i < node.attributes.length; i++) {
        const attr = node.attributes[i];
        attributes[attr.name] = attr.value;
      }
      
      // Preserve section sequence if present by looking at parent
      const parentSection = node.closest('section');
      if (parentSection && parentSection.hasAttribute('seq')) {
         attributes['section_seq'] = parentSection.getAttribute('seq') || '';
      }
      
      // Fix text content parsing, making sure to remove excessive indentation/newlines
      // Wait, node.textContent includes all child text. Let's just use it but trim whitespace.
      const rawText = node.textContent || '';
      const text = rawText.replace(/\s+/g, ' ').trim();
      
      return {
        id: attributes.id || attributes.dlgseq || `dialog-${index}`,
        sectionId: attributes.section_seq || '1',
        character: attributes.character || (node.tagName.toLowerCase() === 'narration' ? 'Narrator' : 'Unknown'),
        text: text,
        attributes: attributes
      };
    });
    
    return {
      fileName: filePath,
      name: chapterName,
      dialogs: dialogs
    };
  };

  const generateXMLFromChapter = (updatedChapter: Chapter): string => {
    let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
    
    // Determine whether this was originally a <story> or <chapter> structure
    const isStoryFormat = updatedChapter.fileName.includes('Story-Entanglement');
    const rootNodeName = isStoryFormat ? 'story' : 'chapter';
    
    xml += `<${rootNodeName}${!isStoryFormat ? ` name="${updatedChapter.name}"` : ''}>\n`;
    
    let currentSection = '';
    
    updatedChapter.dialogs.forEach((dialog, index) => {
      let attrString = '';
      Object.entries(dialog.attributes).forEach(([key, value]) => {
        // Skip structural and internal attributes
        if (key !== 'character' && key !== 'id' && key !== 'dlgseq' && key !== 'section_seq') {
           attrString += ` ${key}="${value}"`;
        }
      });
      
      const nodeName = isStoryFormat && dialog.character === 'Narrator' ? 'narration' : 'dialog';
      
      if (!isStoryFormat || dialog.character !== 'Narrator') {
        attrString = ` character="${dialog.character}"` + attrString;
      }
      
      const idKey = isStoryFormat ? 'dlgseq' : 'id';
      // Format XML with tab characters to match the style of the backup
      const idStr = dialog.id.replace('dialog-', '');
      attrString = ` ${idKey}="${idStr}"` + attrString;
      
      if (isStoryFormat) {
        // Group by section if applicable
        const sectionSeq = dialog.sectionId || dialog.attributes.section_seq as string || '1';
        if (sectionSeq !== currentSection) {
          if (currentSection !== '') {
            xml += `  </section>\n`;
          }
          xml += `  <section seq="${sectionSeq}">\n`;
          currentSection = sectionSeq;
        }
        
        // Wrap text to an 80-character line limit based on word boundaries
        const wrapText = (text: string, indent: string, maxLen: number = 80): string => {
          const words = text.split(' ');
          let lines = [];
          let currentLine = words[0] || '';
          
          for (let i = 1; i < words.length; i++) {
            const word = words[i];
            if (currentLine.length + word.length + 1 > maxLen) {
              lines.push(currentLine);
              currentLine = word;
            } else {
              currentLine += ' ' + word;
            }
          }
          lines.push(currentLine);
          return lines.map(line => `${indent}${line}`).join('\n');
        };
        
        const wrappedText = wrapText(dialog.text, '\t  ');
        xml += `\t<${nodeName}${attrString}>\n${wrappedText}\n\t</${nodeName}>\n`;
        
        // Close last section on final element
        if (index === updatedChapter.dialogs.length - 1) {
          xml += `  </section>\n`;
        }
      } else {
         xml += `  <${nodeName}${attrString}>\n    ${dialog.text}\n  </${nodeName}>\n`;
      }
    });
    
    xml += `</${rootNodeName}>`;
    return xml;
  };

  const handleUpdateDialog = (id: string, updatedDialog: DialogElement) => {
    if (!chapter) return;
    
    const updatedDialogs = chapter.dialogs.map(d => 
      d.id === id ? updatedDialog : d
    );
    
    const updatedChapter = { ...chapter, dialogs: updatedDialogs };
    setChapter(updatedChapter);
    
    // Update the XML representation so TopBar can save it
    setXmlContent(generateXMLFromChapter(updatedChapter));
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowChapterMenu(true);
    setMenuPos({ x: e.pageX, y: e.pageY });
  };

  const closeMenu = () => {
    setShowChapterMenu(false);
  };

  const handleChapterSelect = async (filePath: string) => {
    closeMenu();
    setLoading(true);
    await loadChapter(filePath);
    setLoading(false);
  };

  const triggerRenderCooldown = () => {
    setIsRenderCooldown(true);
    setTimeout(() => {
      setIsRenderCooldown(false);
    }, 10000);
  };

  const refreshClips = async () => {
    const chapterName = currentChapterFile.split('/').pop() || '';
    if (chapterName) {
       const clips = await PythonBridgeService.listChapterClips(chapterName);
       setAvailableClips(clips);
       const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
       setHasChapterAudio(hasAudio);
    }
  };

  if (loading) {
    return <div className="loading-screen">Loading FlexiTTS...</div>;
  }

  if (error) {
    return <div className="error-screen">Error initializing app: {error}</div>;
  }

  return (
    <div className="app-container" onContextMenu={handleContextMenu} onClick={closeMenu}>
      {chapter && (
        <TopBar 
          chapter={chapter} 
          xmlContent={xmlContent} 
          filePath={currentChapterFile} 
          chapterList={chapterList}
          hasChapterAudio={hasChapterAudio}
          selectedCharacter={selectedCharacterFilter}
          onChapterSelect={handleChapterSelect}
          onCharacterSelect={setSelectedCharacterFilter}
          onRenderComplete={refreshClips}
          isRenderCooldown={isRenderCooldown}
          triggerRenderCooldown={triggerRenderCooldown}
        />
      )}
      
      <main className="window-body" style={{ padding: '20px' }}>
        <h2>Dialogs</h2>
        {chapter?.dialogs.map(dialog => {
          const isFilteredOut = selectedCharacterFilter !== '' && dialog.character !== selectedCharacterFilter;
          const displayId = dialog.sectionId ? `${dialog.sectionId}.${dialog.id}` : dialog.id;
          
          // Determine if we have a generated audio clip matching this dialog
          const chapNumMatch = chapter.fileName.match(/(\d+)/);
          const chapNum = chapNumMatch ? chapNumMatch[1].padStart(3, '0') : '000';
          const secStr = (dialog.sectionId || '1').padStart(3, '0');
          const dlgStr = dialog.id.replace('dialog-', '').padStart(3, '0');
          
          // Example: chapter_001_001_001_narrator.wav or chapter_001_001_001.wav
          // We'll check if any file in availableClips contains this sequence
          const searchStr = `chapter_${chapNum}_${secStr}_${dlgStr}`;
          const hasClip = availableClips.some(clipName => clipName.includes(searchStr));

          return (
            <DialogBar 
              key={`${dialog.sectionId || '1'}-${dialog.id}`} 
              dialog={dialog} 
              displayId={displayId}
              chapterFileName={chapter.fileName.split('/').pop()}
              isFilteredOut={isFilteredOut}
              hasAudioClip={hasClip}
              isRenderCooldown={isRenderCooldown}
              onUpdateDialog={handleUpdateDialog} 
              onRefreshClips={refreshClips}
              triggerRenderCooldown={triggerRenderCooldown}
            />
          );
        })}
      </main>

      {showChapterMenu && (
        <div 
          className="context-menu"
          style={{
            position: 'fixed',
            top: menuPos.y,
            left: menuPos.x,
            backgroundColor: 'white',
            border: '1px solid #ccc',
            boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
            zIndex: 1000,
            padding: '5px 0',
            minWidth: '200px'
          }}
        >
          <div style={{ padding: '5px 10px', fontWeight: 'bold', borderBottom: '1px solid #eee', color: '#333' }}>
            Select Chapter
          </div>
          {chapterList.length > 0 ? (
            chapterList.map((chFile, idx) => {
              const chFileName = chFile.split('/').pop() || chFile;
              return (
              <div 
                key={idx} 
                style={{ 
                  padding: '5px 15px', 
                  cursor: 'pointer', 
                  color: '#333',
                  backgroundColor: chFile === currentChapterFile ? '#e6f7ff' : 'transparent',
                  fontWeight: chFile === currentChapterFile ? 'bold' : 'normal'
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleChapterSelect(chFile);
                }}
                onMouseEnter={(e) => {
                  if (chFile !== currentChapterFile) e.currentTarget.style.backgroundColor = '#f0f0f0';
                }}
                onMouseLeave={(e) => {
                  if (chFile !== currentChapterFile) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                {chFileName}
              </div>
            )})
          ) : (
            <div style={{ padding: '5px 15px', color: '#999', fontStyle: 'italic' }}>
              No chapters found
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
