import type { Chapter } from '../models/types';

/**
 * Wraps text to specified max length without breaking words.
 * @param text - The text to wrap
 * @param indent - The indentation string for each line
 * @param maxLen - Maximum line length (default: 80)
 * @returns The wrapped text with newlines and indentation
 */
export const wrapText = (text: string, indent: string, maxLen: number = 80): string => {
  const words = text.split(' ');
  if (words.length === 0) return '';
  
  const lines: string[] = [];
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

/**
 * Determines the root node name (story or chapter) based on filename.
 * @param fileName - The chapter filename
 * @returns 'story' for Story-Entanglement files, 'chapter' otherwise
 */
export const getRootNodeName = (fileName: string): string => {
  return fileName.includes('Story-Entanglement') ? 'story' : 'chapter';
};

/**
 * Filters out structural attributes that shouldn't be written to XML.
 * @param attributes - The dialog attributes
 * @returns XML attribute string
 */
export const buildAttributeString = (attributes: Record<string, string>): string => {
  let attrString = '';
  Object.entries(attributes).forEach(([key, value]) => {
    // Skip structural and internal attributes
    if (key !== 'character' && key !== 'id' && key !== 'dlgseq' && key !== 'section_seq') {
      attrString += ` ${key}="${value}"`;
    }
  });
  return attrString;
};

/**
 * Determines the XML node name based on character and story format.
 * @param character - The character name
 * @param isStoryFormat - Whether this is a story format
 * @returns 'narration' for narrator in story format, 'dialog' otherwise
 */
export const getNodeName = (character: string, isStoryFormat: boolean): string => {
  return isStoryFormat && character === 'Narrator' ? 'narration' : 'dialog';
};

/**
 * Gets the ID attribute key based on format.
 * @param isStoryFormat - Whether this is a story format
 * @returns 'dlgseq' for story format, 'id' for chapter format
 */
export const getIdKey = (isStoryFormat: boolean): string => {
  return isStoryFormat ? 'dlgseq' : 'id';
};

/**
 * Generates an XML string from a Chapter object.
 * Handles both <story> and <chapter> formats with section grouping.
 * 
 * @param updatedChapter - The chapter data to serialize to XML
 * @returns The generated XML string
 */
export const generateXMLFromChapter = (updatedChapter: Chapter): string => {
  let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
  
  const isStoryFormat = getRootNodeName(updatedChapter.fileName) === 'story';
  const rootNodeName = isStoryFormat ? 'story' : 'chapter';
  
  xml += `<${rootNodeName}${!isStoryFormat ? ` name="${updatedChapter.name}"` : ''}>\n`;
  
  let currentSection = '';
  
  updatedChapter.dialogs.forEach((dialog, index) => {
    let attrString = buildAttributeString(dialog.attributes);
    const nodeName = getNodeName(dialog.character, isStoryFormat);
    
    // Add character attribute if not narrator in story format
    if (!isStoryFormat || dialog.character !== 'Narrator') {
      attrString = ` character="${dialog.character}"` + attrString;
    }
    
    // Add ID attribute
    const idKey = getIdKey(isStoryFormat);
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
