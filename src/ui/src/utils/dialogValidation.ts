import type { DialogElement, StoryConfig } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';

export interface DialogValidationIssue {
  code: 'missing-character' | 'invalid-custom-voice' | 'invalid-voice-sample' | 'invalid-dialog-effects';
  message: string;
}

export type DialogValidationMap = Record<string, DialogValidationIssue[]>;

const QWEN3_DOC_SUPPORTED_SPEAKERS = new Set([
  'vivian',
  'serena',
  'uncle_fu',
  'dylan',
  'eric',
  'ryan',
  'aiden',
  'ono_anna',
  'sohee',
]);

const normalize = (value: string | undefined | null): string => String(value || '').trim().toLowerCase();

const normalizeSpeakerFileName = (value: string): string => {
  const trimmed = String(value || '').trim();
  return trimmed.replace(/-x(?=\.[^.]+$)/i, '');
};

const dialogKey = (dialog: DialogElement): string => `${dialog.sectionId || '0'}::${dialog.dlgseq}::${dialog._index ?? ''}`;

export const getDialogValidationKey = dialogKey;

export async function validateChapterDialogs(chapterDialogs: DialogElement[], config: StoryConfig | null, storyDir?: string): Promise<DialogValidationMap> {
  const result: DialogValidationMap = {};
  if (!config) return result;

  console.log('[dialogValidation] validateChapterDialogs:start', {
    storyDir,
    dialogCount: chapterDialogs.length,
    configCharacters: (config.characters || []).map((character) => character.name),
  });

  const characterMap = new Map(
    (config.characters || []).map((character) => [normalize(character.name), character])
  );
  const namedDialogEffects = new Set(
    (config['dialog-effects'] || [])
      .map((effect: any) => String(effect?.name || '').trim())
      .filter(Boolean)
      .map((name: string) => name.toLowerCase())
  );

  for (const dialog of chapterDialogs) {
    const characterName = normalize(dialog.character);
    console.log('[dialogValidation] dialog:inspect', {
      rawCharacter: dialog.character,
      normalizedCharacter: characterName,
      key: dialogKey(dialog),
    });
    if (!characterName || characterName === 'narrator') {
      console.log('[dialogValidation] dialog:skip', { reason: 'empty-or-narrator', character: dialog.character });
      continue;
    }

    const issues: DialogValidationIssue[] = [];
    const charConfig = characterMap.get(characterName);

    if (!charConfig) {
      console.log('[dialogValidation] dialog:missing-character', {
        character: dialog.character,
        availableCharacters: Array.from(characterMap.keys()),
      });
      issues.push({
        code: 'missing-character',
        message: `Character '${dialog.character}' is referenced in Chapter-Dialog XML but missing from story-config.yml.`,
      });
    } else {
      console.log('[dialogValidation] dialog:found-character-config', {
        character: dialog.character,
        config: charConfig,
      });
      const configuredDialogEffects = Array.isArray(charConfig['dialog-effects']) ? charConfig['dialog-effects'] : [];
      console.log('[dialogValidation] dialog:configured-dialog-effects', {
        character: dialog.character,
        configuredDialogEffects,
        namedDialogEffects: Array.from(namedDialogEffects),
      });
      const invalidDialogEffects = configuredDialogEffects
        .map((effectName) => String(effectName || '').trim())
        .filter(Boolean)
        .filter((effectName) => !namedDialogEffects.has(effectName.toLowerCase()));

      if (invalidDialogEffects.length > 0) {
        const quotedEffects = invalidDialogEffects.map((effectName) => `'${effectName}'`).join(', ');
        console.log('[dialogValidation] dialog:invalid-dialog-effects', {
          character: dialog.character,
          invalidDialogEffects,
          namedDialogEffects: Array.from(namedDialogEffects),
        });
        issues.push({
          code: 'invalid-dialog-effects',
          message: `Character '${dialog.character}' dialog-effects entries ${quotedEffects} are not defined in story-config.yml dialog-effects.`,
        });
      }

      if (charConfig['custom-voice']) {
        const speaker = String(charConfig['custom-voice']?.speaker || '').trim();
        if (!speaker) {
          issues.push({
            code: 'invalid-custom-voice',
            message: `Character '${dialog.character}' has custom-voice configured, but speaker is missing.`,
          });
        } else if (!QWEN3_DOC_SUPPORTED_SPEAKERS.has(speaker.toLowerCase())) {
          issues.push({
            code: 'invalid-custom-voice',
            message: `Character '${dialog.character}' custom-voice speaker '${speaker}' is not a documented Qwen3-TTS speaker.`,
          });
        }
      } else {
        const voiceSample = String(charConfig['voice-sample'] || '').trim();
        if (!voiceSample) {
          issues.push({
            code: 'invalid-voice-sample',
            message: `Character '${dialog.character}' has no voice-sample configured.`,
          });
        } else if (storyDir) {
          const voiceRoot = String(config.global?.voices || '').trim().replace(/^\/+/, '').replace(/\/+$/, '');
          const normalizedVoiceSample = normalizeSpeakerFileName(voiceSample);
          const candidatePaths = [
            voiceSample,
            normalizedVoiceSample,
            voiceRoot ? `${voiceRoot}/${voiceSample}` : voiceSample,
            voiceRoot ? `${voiceRoot}/${normalizedVoiceSample}` : normalizedVoiceSample,
          ].filter((value, index, array) => value && array.indexOf(value) === index);

          let exists = false;
          for (const candidatePath of candidatePaths) {
            exists = await PythonBridgeService.checkStoryFileExists(storyDir, candidatePath);
            console.log('[dialogValidation] dialog:check-voice-sample', {
              character: dialog.character,
              storyDir,
              candidatePath,
              exists,
            });
            if (exists) {
              break;
            }
          }

          if (!exists) {
            console.log('[dialogValidation] dialog:invalid-voice-sample', {
              character: dialog.character,
              voiceSample,
              storyDir,
              candidatePaths,
            });
            issues.push({
              code: 'invalid-voice-sample',
              message: `Character '${dialog.character}' voice-sample '${voiceSample}' does not exist in ${storyDir}.`,
            });
          }
        }
      }
    }

    if (issues.length > 0) {
      console.log('[dialogValidation] dialog:issues', {
        character: dialog.character,
        key: dialogKey(dialog),
        issues,
      });
      result[dialogKey(dialog)] = issues;
    } else {
      console.log('[dialogValidation] dialog:no-issues', {
        character: dialog.character,
        key: dialogKey(dialog),
      });
    }
  }

  console.log('[dialogValidation] validateChapterDialogs:done', { resultKeys: Object.keys(result) });
  return result;
}
