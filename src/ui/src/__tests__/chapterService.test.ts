import { describe, it, expect } from 'vitest';
import { 
  generateXMLFromChapter, 
  wrapText, 
  getRootNodeName, 
  buildAttributeString,
  getNodeName,
  getIdKey
} from '../services/chapterService';
import type { Chapter, DialogElement } from '../models/types';

// Sample chapter data for testing
const createDialog = (overrides?: Partial<DialogElement>): DialogElement => ({
  _index: 0,
  dlgseq: '1',
  sectionId: '1',
  character: 'Test Character',
  text: 'Hello world!',
  attributes: { dlgseq: '1', character: 'Test Character', emotion: 'happy' },
  ...overrides,
});

const createMockChapter = (overrides?: Partial<Chapter>): Chapter => ({
  fileName: 'test-chapter.xml',
  name: 'Test Chapter',
  dialogs: [createDialog()],
  ...overrides
});

describe('chapterService', () => {
  describe('wrapText', () => {
    it('should wrap text at word boundaries', () => {
      const longText = 'This is a very long text that needs to be wrapped because it exceeds the limit';
      const result = wrapText(longText, '  ', 20);
      const lines = result.split('\n');
      expect(lines.every(line => line.length <= 22)).toBe(true); // +2 for indent
    });

    it('should handle short text without wrapping', () => {
      const shortText = 'Short text';
      const result = wrapText(shortText, '', 80);
      expect(result).toBe(shortText);
    });

    it('should apply indentation to wrapped lines', () => {
      const text = 'word1 word2 word3';
      const result = wrapText(text, '\t  ', 10);
      expect(result).toContain('\t  ');
    });

    it('should handle empty text', () => {
      const result = wrapText('', '');
      expect(result).toBe('');
    });
  });

  describe('getRootNodeName', () => {
    it('should return "story" for Story-Entanglement files', () => {
      expect(getRootNodeName('Story-Entanglement/story-xml/test.xml')).toBe('story');
      expect(getRootNodeName('Story-Entanglement/story-chapters/test.md')).toBe('story');
    });

    it('should return "chapter" for other files', () => {
      expect(getRootNodeName('other/path/test.xml')).toBe('chapter');
      expect(getRootNodeName('test.xml')).toBe('chapter');
    });
  });

  describe('buildAttributeString', () => {
    it('should filter out structural attributes', () => {
      const attrs = {
        id: '1',
        character: 'Test',
        emotion: 'happy',
        dlgseq: '1',
        section_seq: '1'
      };
      const result = buildAttributeString(attrs);
      expect(result).toContain('emotion="happy"');
      expect(result).not.toContain('id=');
      expect(result).not.toContain('character=');
      expect(result).not.toContain('dlgseq=');
      expect(result).not.toContain('section_seq=');
    });

    it('should return empty string for no valid attributes', () => {
      const attrs = { id: '1', character: 'Test' };
      expect(buildAttributeString(attrs)).toBe('');
    });
  });

  describe('getNodeName', () => {
    it('should return "narration" for Narrator in story format', () => {
      expect(getNodeName('Narrator', true)).toBe('narration');
    });

    it('should return "dialog" for other characters in story format', () => {
      expect(getNodeName('Alice', true)).toBe('dialog');
    });

    it('should return "dialog" for all characters in chapter format', () => {
      expect(getNodeName('Narrator', false)).toBe('dialog');
      expect(getNodeName('Alice', false)).toBe('dialog');
    });
  });

  describe('getIdKey', () => {
    it('should always return "dlgseq"', () => {
      expect(getIdKey()).toBe('dlgseq');
    });
  });

  describe('generateXMLFromChapter', () => {
    it('should generate basic chapter XML', () => {
      const chapter = createMockChapter({ fileName: 'test.xml' });
      const xml = generateXMLFromChapter(chapter);
      
      expect(xml).toContain('<?xml version="1.0" encoding="UTF-8"?>');
      expect(xml).toContain('<chapter name="Test Chapter">');
      expect(xml).toContain('</dialog>');
      expect(xml).toContain('</chapter>');
    });

    it('should generate story format XML for Story-Entanglement files', () => {
      const chapter = createMockChapter({ 
        fileName: 'Story-Entanglement/story-xml/test.xml' 
      });
      const xml = generateXMLFromChapter(chapter);
      
      expect(xml).toContain('<story>');
      expect(xml).not.toContain('name="Test Chapter"');
    });

    it('should include character attribute for non-narrator dialogs', () => {
      const chapter = createMockChapter({
        fileName: 'test.xml',
        dialogs: [createDialog({ text: 'Hello', attributes: { dlgseq: '1', character: 'Test Character' } })]
      });
      const xml = generateXMLFromChapter(chapter);
      expect(xml).toContain('character="Test Character"');
    });

    it('should wrap dialogs in sections for story format', () => {
      const chapter = createMockChapter({
        fileName: 'Story-Entanglement/story-xml/test.xml',
        dialogs: [
          createDialog({ _index: 0, dlgseq: '1', sectionId: '1', character: 'Character1', text: 'Line 1', attributes: { dlgseq: '1', character: 'Character1' } }),
          createDialog({ _index: 1, dlgseq: '2', sectionId: '2', character: 'Character2', text: 'Line 2', attributes: { dlgseq: '2', character: 'Character2' } })
        ]
      });
      const xml = generateXMLFromChapter(chapter);
      
      expect(xml).toContain('<section seq="1">');
      expect(xml).toContain('<section seq="2">');
      expect(xml).toContain('</dialog>');
    });

    it('should use narration node for Narrator in story format', () => {
      const chapter = createMockChapter({
        fileName: 'Story-Entanglement/story-xml/test.xml',
        dialogs: [createDialog({ _index: 0, dlgseq: '1', sectionId: '1', character: 'Narrator', text: 'Some narration text', attributes: { dlgseq: '1', character: 'Narrator' } })]
      });
      const xml = generateXMLFromChapter(chapter);
      expect(xml).toContain('<narration');
      expect(xml).toContain('</narration>');
      expect(xml).not.toContain('character="Narrator"'); // Should be omitted in story format
    });

    it('should preserve custom attributes', () => {
      const chapter = createMockChapter({
        dialogs: [createDialog({ _index: 0, dlgseq: '1', sectionId: '1', character: 'Test', text: 'Hello', attributes: { dlgseq: '1', character: 'Test', emotion: 'happy', volume: 'loud' } })]
      });
      const xml = generateXMLFromChapter(chapter);
      expect(xml).toContain('emotion="happy"');
      expect(xml).toContain('volume="loud"');
    });

    it('should wrap long text content', () => {
      const longText = 'This is a very long text that needs wrapping because it exceeds the word limit';
      const chapter = createMockChapter({
        fileName: 'Story-Entanglement/story-xml/test.xml',
        dialogs: [createDialog({ _index: 0, dlgseq: '1', sectionId: '1', character: 'Test', text: longText, attributes: { dlgseq: '1', character: 'Test' } })]
      });
      const xml = generateXMLFromChapter(chapter);
      // In story format, long text should be wrapped
      expect(xml.split('\n').length).toBeGreaterThan(1);
    });

    it('should match snapshot for basic chapter', () => {
      const chapter = createMockChapter();
      const xml = generateXMLFromChapter(chapter);
      expect(xml).toMatchSnapshot('basic-chapter');
    });

    it('should match snapshot for story format', () => {
      const chapter = createMockChapter({
        fileName: 'Story-Entanglement/story-xml/test.xml',
        dialogs: [
          createDialog({ _index: 0, dlgseq: '1', sectionId: '1', character: 'Narrator', text: 'Opening narration', attributes: { dlgseq: '1', character: 'Narrator' }}),
          createDialog({ _index: 1, dlgseq: '2', sectionId: '1', character: 'Alice', text: 'Hello Bob', attributes: { dlgseq: '2', character: 'Alice' }}),
          createDialog({ _index: 2, dlgseq: '3', sectionId: '2', character: 'Bob', text: 'Hi Alice', attributes: { dlgseq: '3', character: 'Bob' }})
        ]
      });
      const xml = generateXMLFromChapter(chapter);
      expect(xml).toMatchSnapshot('story-format');
    });
  });
});
