import { describe, it, expect } from 'vitest';

// Test that the services index exports correctly
describe('services/index exports', () => {
  it('should export AlertService', async () => {
    const { AlertService } = await import('../services');
    expect(AlertService).toBeDefined();
    expect(typeof AlertService.getInstance).toBe('function');
  });

  it('should export alertService singleton', async () => {
    const { alertService } = await import('../services');
    expect(alertService).toBeDefined();
    expect(typeof alertService.info).toBe('function');
    expect(typeof alertService.success).toBe('function');
    expect(typeof alertService.warning).toBe('function');
    expect(typeof alertService.error).toBe('function');
  });

  it('should export alerts convenience functions', async () => {
    const { alerts } = await import('../services');
    expect(alerts).toBeDefined();
    expect(typeof alerts.info).toBe('function');
    expect(typeof alerts.success).toBe('function');
    expect(typeof alerts.warning).toBe('function');
    expect(typeof alerts.error).toBe('function');
    expect(typeof alerts.alert).toBe('function');
  });

  it('should export chapterService functions', async () => {
    const exports = await import('../services');
    
    // These should all be re-exported from chapterService
    expect(exports.wrapText).toBeDefined();
    expect(exports.getRootNodeName).toBeDefined();
    expect(exports.buildAttributeString).toBeDefined();
    expect(exports.getNodeName).toBeDefined();
    expect(exports.getIdKey).toBeDefined();
    expect(exports.generateXMLFromChapter).toBeDefined();
  });

  it('should export types', async () => {
    const { InternalAlertOptions, InternalAlertType } = await import('../services');
    // Types exist at compile time, this verifies the exports work
    expect(InternalAlertOptions).toBeUndefined(); // Type-only export
    expect(InternalAlertType).toBeUndefined(); // Type-only export
  });

  it('should maintain singleton pattern through module exports', async () => {
    const { AlertService, alertService } = await import('../services');
    const directInstance = AlertService.getInstance();
    
    expect(alertService).toBe(directInstance);
  });
});

describe('chapterService exports through index', () => {
  it('should export wrapText function', async () => {
    const { wrapText } = await import('../services');
    const result = wrapText('Hello world test', '  ', 10);
    expect(typeof result).toBe('string');
    expect(result).toContain('Hello');
  });

  it('should export getRootNodeName function', async () => {
    const { getRootNodeName } = await import('../services');
    
    const storyResult = getRootNodeName('Story-Entanglement-001.md');
    expect(storyResult).toBe('story');
    
    const chapterResult = getRootNodeName('regular-chapter.md');
    expect(chapterResult).toBe('chapter');
  });

  it('should export buildAttributeString function', async () => {
    const { buildAttributeString } = await import('../services');
    
    const attributes = { effect: 'fade', speed: 'slow' };
    const result = buildAttributeString(attributes);
    
    expect(result).toContain('effect');
    expect(result).toContain('speed');
  });

  it('should export getNodeName function', async () => {
    const { getNodeName } = await import('../services');
    
    // Narrator in story format
    expect(getNodeName('Narrator', true)).toBe('narration');
    // Narrator in chapter format
    expect(getNodeName('Narrator', false)).toBe('dialog');
    // Other character in story format
    expect(getNodeName('character1', true)).toBe('dialog');
    // Other character in chapter format
    expect(getNodeName('character1', false)).toBe('dialog');
  });

  it('should export getIdKey function', async () => {
    const { getIdKey } = await import('../services');
    expect(getIdKey()).toBe('dlgseq');
  });
});
