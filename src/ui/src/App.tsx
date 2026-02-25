import { useState, useEffect } from 'react';
import './App.css';
import { PythonBridgeService } from './services/pythonBridge';
import type { StoryConfig, Chapter, DialogElement } from './models/types';
import { TopBar } from './components/TopBar';
import { DialogBar } from './components/DialogBar';

function App() {
  // We don't use config directly in rendering right now, but we validate and load it
  const [config, setConfig] = useState<StoryConfig | null>(null);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [xmlContent, setXmlContent] = useState<string>('');
  const [lastSavedXml, setLastSavedXml] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Context menu state
  const [showChapterMenu, setShowChapterMenu] = useState(false);
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });
  const [chapterList, setChapterList] = useState<string[]>([]);
  const [selectedCharacterFilter, setSelectedCharacterFilter] = useState<string>('');

  // In a real app this would come from the user's selection
  const [currentChapterFile, setCurrentChapterFile] = useState<string>('');
  const [availableClips, setAvailableClips] = useState<string[]>([]);
  const [hasChapterAudio, setHasChapterAudio] = useState(false);
  const [isGeneratingStructure, setIsGeneratingStructure] = useState(false);
  const [generateAttempt, setGenerateAttempt] = useState(0);

  useEffect(() => {
    const initApp = async () => {
      try {
        setLoading(true);
        
        // Load configuration
        await PythonBridgeService.validateConfig();
        const loadedConfig = await PythonBridgeService.loadStoryConfig();
        setConfig(loadedConfig);
        
        // Load chapter list first (now primarily reading .md files)
        const fetchedList = await PythonBridgeService.listChapterFiles();
        setChapterList(fetchedList);

        if (fetchedList.length > 0) {
           await handleChapterSelect(fetchedList[0], loadedConfig);
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

  const loadChapter = async (filePath: string, loadedConfig?: StoryConfig) => {
    try {
      console.log(`Loading chapter: ${filePath}`);
      // Only attempt to read and validate if the file exists. If it doesn't exist, we will fail cleanly.
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
      console.log("Config characters check:", (loadedConfig || config)?.characters);
      // Let handleChapterSelect manage currentChapterFile state to avoid flipping it back to xml
      setSelectedCharacterFilter(''); // reset filter on load
      
      const chapterName = filePath.split('/').pop() || '';
      if (chapterName) {
         const clips = await PythonBridgeService.listChapterClips(chapterName);
         setAvailableClips(clips);
         const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
         setHasChapterAudio(hasAudio);
      }
      
      const newXml = generateXMLFromChapter(parsedChapter);
      setXmlContent(newXml);
      setLastSavedXml(newXml);
      setHasUnsavedChanges(false);
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
        _index: index, // Add internal index for strict array positioning
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

  const handleUpdateDialog = (id: string, sectionId: string, updatedDialog: DialogElement) => {
    if (!chapter) return;
    
    // We update by mapping over the array to guarantee the strict array sequence is maintained
    const updatedDialogs = chapter.dialogs.map(d => {
      // Use the internal _index if available, otherwise fallback to matching id/sectionId combo
      const isMatch = updatedDialog._index !== undefined && d._index !== undefined 
         ? d._index === updatedDialog._index 
         : d.id === id && (d.sectionId || '1') === sectionId;
         
      return isMatch ? updatedDialog : d;
    });
    
    const updatedChapter = { ...chapter, dialogs: updatedDialogs };
    setChapter(updatedChapter);
    
    // Update the XML representation so TopBar can save it
    const newXml = generateXMLFromChapter(updatedChapter);
    setXmlContent(newXml);
    setHasUnsavedChanges(newXml !== lastSavedXml);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowChapterMenu(true);
    setMenuPos({ x: e.pageX, y: e.pageY });
  };

  const closeMenu = () => {
    setShowChapterMenu(false);
  };

  const handleChapterSelect = async (filePath: string, loadedConfig?: StoryConfig) => {
    closeMenu();

    if (hasUnsavedChanges && currentChapterFile) {
      const title = "Unsaved Changes";
      const message = "You have unsaved changes in the current chapter.";
      const detail = "Do you want to save them before switching chapters?";
      
      const res = await PythonBridgeService.showConfirmDialog(title, message, detail);
      if (res === 2) {
        // Cancel
        return;
      } else if (res === 0) {
        // Save
        try {
          // Determine the xml path corresponding to the old markdown path
          const stem = currentChapterFile.split('/').pop()?.replace('.md', '') || 'unknown';
          const xmlPath = `Story-Entanglement/story-xml/${stem}.xml`;
          await PythonBridgeService.writeChapterFile(xmlPath, xmlContent);
          await PythonBridgeService.validateChapterXML(xmlPath);
          setHasUnsavedChanges(false);
          setLastSavedXml(xmlContent);
        } catch (error) {
          console.error("Save failed during chapter switch", error);
          // abort switch if save fails
          return;
        }
      }
      // if res === 1 (Discard), just proceed without saving
    }

    setLoading(true);
    setCurrentChapterFile(filePath); // Always set the selected markdown file path in TopBar

    // Determine target XML path
    const stem = filePath.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || 'unknown';
    const xmlPath = `Story-Entanglement/story-xml/${stem}.xml`;

    // Check if XML exists for this Markdown file
    const xmlExists = await PythonBridgeService.checkXmlExists(stem);

    if (xmlExists) {
      await loadChapter(xmlPath, loadedConfig);
      setLoading(false);
    } else {
      // Missing XML -> Generation Pipeline
      setLoading(false);
      setIsGeneratingStructure(true);
      setGenerateAttempt(1);
      
      try {
        await runXmlGenerationPipeline(stem, 1);
        // On success, load it
        await loadChapter(xmlPath, loadedConfig);
      } catch (err: any) {
        console.error("XML Generation Pipeline failed entirely:", err);
        await PythonBridgeService.showErrorDialog(
          "Generation Failed",
          `Could not generate valid XML for ${stem} after 3 attempts. Please check your raw Markdown file for unsupported formatting.\n\nError: ${err.message}`
        );
      } finally {
        setIsGeneratingStructure(false);
      }
    }
  };

  const runXmlGenerationPipeline = async (stem: string, attempt: number): Promise<void> => {
    if (attempt > 3) {
      throw new Error("Exceeded maximum retry attempts (3).");
    }
    setGenerateAttempt(attempt);

    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        console.log(`[Pipeline] Attempt ${attempt}: Running chapter_to_xml.py on ${stem}`);
        await window.api.runPythonScript('src/scripts/chapter_to_xml.py', [`Story-Entanglement/story-chapters/${stem}.md`]);
        
        console.log(`[Pipeline] Attempt ${attempt}: Running chapter_seq_xml.py on ${stem}`);
        await window.api.runPythonScript('src/scripts/chapter_seq_xml.py', [`Story-Entanglement/story-xml/${stem}.xml`]);
        
        console.log(`[Pipeline] Attempt ${attempt}: Running chapter_validate_xml.py on ${stem}`);
        await window.api.runPythonScript('src/scripts/chapter_validate_xml.py', [`Story-Entanglement/story-xml/${stem}.xml`]);
      } else {
        // Mock fallback
        console.log(`[Mock Pipeline] Attempt ${attempt} for ${stem}`);
        await new Promise(r => setTimeout(r, 2000));
      }
    } catch (err: any) {
      console.warn(`[Pipeline] Attempt ${attempt} failed:`, err);
      if (attempt >= 3) {
        throw err;
      }
      await runXmlGenerationPipeline(stem, attempt + 1);
    }
  };

  const handleSave = async () => {
    try {
        const stem = currentChapterFile.split('/').pop()?.replace('.md', '') || 'unknown';
        const xmlPath = `Story-Entanglement/story-xml/${stem}.xml`;
        await PythonBridgeService.writeChapterFile(xmlPath, xmlContent);
        await PythonBridgeService.validateChapterXML(xmlPath);
        setLastSavedXml(xmlContent);
        setHasUnsavedChanges(false);
    } catch(err) {
        console.error("Save failed:", err);
    }
  };

  const refreshClips = async () => {
    const chapterName = currentChapterFile.split('/').pop()?.replace('.md', '.xml') || '';
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
      {isGeneratingStructure && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 9999,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          color: 'white', fontFamily: 'sans-serif'
        }}>
          <div className="spinner-icon" style={{ 
            width: '40px', height: '40px',
            border: '4px solid rgba(255,255,255,0.3)',
            borderRadius: '50%', borderTopColor: '#4CAF50',
            animation: 'spin 1s ease-in-out infinite',
            marginBottom: '20px'
          }}></div>
          <h2>Processing Markdown...</h2>
          <p>Generating XML structure (Attempt {generateAttempt}/3)</p>
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {chapter && (
        <TopBar 
          config={config}
          chapter={chapter} 
          filePath={currentChapterFile} 
          chapterList={chapterList}
          hasChapterAudio={hasChapterAudio}
          selectedCharacter={selectedCharacterFilter}
          onChapterSelect={handleChapterSelect}
          onCharacterSelect={setSelectedCharacterFilter}
          onSave={handleSave}
          onRenderComplete={refreshClips}
          hasUnsavedChanges={hasUnsavedChanges}
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
              key={`${dialog.sectionId || '1'}-${dialog.id}-${dialog._index}`} 
              dialog={dialog} 
              displayId={displayId}
              chapterFileName={chapter.fileName.split('/').pop()}
              isFilteredOut={isFilteredOut}
              hasAudioClip={hasClip}
              onSaveRequest={handleSave}
              onUpdateDialog={handleUpdateDialog} 
              onRefreshClips={refreshClips}
              availableCharacters={config?.characters?.map(c => c.name) || []}
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
              const chFileName = chFile.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || chFile;
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
              );
            })
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
