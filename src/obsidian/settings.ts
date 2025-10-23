export interface UnityLangPXSettings {
	serviceUrl: string;
	sourceLanguage: string;
	targetLanguage: string;
	defaultOutputMode: 'suffix' | 'overwrite' | 'custom';
	autoDetectService: boolean;
	translationHistory: TranslationHistoryEntry[];
}

export interface TranslationHistoryEntry {
	id: string;
	source_file: string;
	source_language: string;
	target_language: string;
	timestamp: string;
	duration: number;
	chars_translated: number;
}

export const DEFAULT_SETTINGS: UnityLangPXSettings = {
	serviceUrl: 'http://localhost:8848',
	sourceLanguage: 'en',
	targetLanguage: 'zh',
	defaultOutputMode: 'suffix',
	autoDetectService: true,
	translationHistory: []
};