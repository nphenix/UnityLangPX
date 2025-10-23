export interface ServiceStatus {
	running: boolean;
	port?: number;
	version?: string;
	models_available?: string[];
	error?: string;
}

export interface TranslationOptions {
	source_language: string;
	target_language: string;
	output_mode: 'suffix' | 'overwrite' | 'custom';
	output_path?: string;
	overwrite?: boolean;
}

export interface TranslationRequest {
	file_path: string;
	content: string;
	source_language: string;
	target_language: string;
	output_mode: 'suffix' | 'overwrite' | 'custom';
	output_path?: string;
	overwrite?: boolean;
}

export interface TranslationResult {
	success: boolean;
	translated_content?: string;
	output_path?: string;
	duration?: number;
	chars_translated?: number;
	error?: string;
}

export interface ServiceStartResult {
	success: boolean;
	port?: number;
	message?: string;
	error?: string;
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