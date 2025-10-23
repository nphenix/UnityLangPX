import axios, { AxiosInstance } from 'axios';
import { UnityLangPXSettings } from '../settings';
import { 
	ServiceStatus, 
	TranslationRequest, 
	TranslationResult, 
	ServiceStartResult,
	TranslationHistoryEntry
} from './types';

export class TranslationAPI {
	private client: AxiosInstance;
	private settings: UnityLangPXSettings;

	constructor(settings: UnityLangPXSettings) {
		this.settings = settings;
		this.client = axios.create({
			baseURL: settings.serviceUrl,
			timeout: 30000,
			headers: {
				'Content-Type': 'application/json',
			},
		});

		// 请求拦截器
		this.client.interceptors.request.use(
			(config) => {
				console.log(`API请求: ${config.method?.toUpperCase()} ${config.url}`);
				return config;
			},
			(error) => {
				console.error('API请求错误:', error);
				return Promise.reject(error);
			}
		);

		// 响应拦截器
		this.client.interceptors.response.use(
			(response) => {
				console.log(`API响应: ${response.status} ${response.config.url}`);
				return response;
			},
			(error) => {
				console.error('API响应错误:', error);
				return Promise.reject(error);
			}
		);
	}

	updateSettings(settings: UnityLangPXSettings) {
		this.settings = settings;
		this.client.defaults.baseURL = settings.serviceUrl;
	}

	async checkServiceStatus(): Promise<ServiceStatus> {
		try {
			const response = await this.client.get('/api/service/status');
			return response.data;
		} catch (error) {
			console.error('检查服务状态失败:', error);
			return {
				running: false,
				error: this.getErrorMessage(error)
			};
		}
	}

	async startService(): Promise<ServiceStartResult> {
		try {
			// 在Obsidian插件中，我们不能直接启动Python服务
			// 所以这里只返回一个提示，用户需要手动启动服务
			return {
				success: false,
				error: "请使用CLI命令启动服务: unitylangpx serve"
			};
		} catch (error) {
			console.error('启动服务失败:', error);
			return {
				success: false,
				error: this.getErrorMessage(error)
			};
		}
	}

	async translateFile(request: TranslationRequest): Promise<TranslationResult> {
		try {
			const response = await this.client.post('/api/translate/file', request);
			return response.data;
		} catch (error) {
			console.error('翻译文件失败:', error);
			return {
				success: false,
				error: this.getErrorMessage(error)
			};
		}
	}

	async translateText(text: string, sourceLanguage: string, targetLanguage: string): Promise<TranslationResult> {
		try {
			const response = await this.client.post('/api/translate/text', {
				text,
				source_language: sourceLanguage,
				target_language: targetLanguage,
				preserve_formatting: true
			});
			return response.data;
		} catch (error) {
			console.error('翻译文本失败:', error);
			return {
				success: false,
				error: this.getErrorMessage(error)
			};
		}
	}

	async translateBatch(files: string[], outputDir: string, sourceLanguage: string, targetLanguage: string): Promise<any> {
		try {
			const response = await this.client.post('/api/translate/batch', {
				files,
				output_dir: outputDir,
				source_language: sourceLanguage,
				target_language: targetLanguage,
				overwrite: false
			});
			return response.data;
		} catch (error) {
			console.error('批量翻译失败:', error);
			return {
				success: false,
				error: this.getErrorMessage(error)
			};
		}
	}

	async getTranslationHistory(limit: number = 50, offset: number = 0): Promise<{
		history: TranslationHistoryEntry[];
		total: number;
		limit: number;
		offset: number;
	}> {
		try {
			const response = await this.client.get(`/api/history?limit=${limit}&offset=${offset}`);
			return response.data;
		} catch (error) {
			console.error('获取翻译历史失败:', error);
			return {
				history: [],
				total: 0,
				limit,
				offset
			};
		}
	}

	async clearTranslationHistory(): Promise<{ success: boolean; message?: string; error?: string }> {
		try {
			const response = await this.client.delete('/api/history');
			return response.data;
		} catch (error) {
			console.error('清空翻译历史失败:', error);
			return {
				success: false,
				error: this.getErrorMessage(error)
			};
		}
	}

	private getErrorMessage(error: any): string {
		if (error.response) {
			// 服务器响应了错误状态码
			const status = error.response.status;
			const data = error.response.data;
			
			if (data && data.error) {
				return data.error;
			}
			
			switch (status) {
				case 400:
					return '请求参数错误';
				case 401:
					return '未授权访问';
				case 403:
					return '禁止访问';
				case 404:
					return '服务端点不存在';
				case 500:
					return '服务器内部错误';
				case 502:
					return '网关错误';
				case 503:
					return '服务不可用';
				case 504:
					return '网关超时';
				default:
					return `服务器错误 (${status})`;
			}
		} else if (error.request) {
			// 请求已发出，但没有收到响应
			return '无法连接到服务器，请检查服务是否运行';
		} else {
			// 设置请求时发生错误
			return error.message || '未知错误';
		}
	}

	async findAvailablePort(startPort: number = 8848, endPort: number = 8898): Promise<number> {
		for (let port = startPort; port <= endPort; port++) {
			try {
				const testUrl = this.settings.serviceUrl.replace(/:\d+/, `:${port}`);
				await axios.get(`${testUrl}/api/service/status`, { timeout: 1000 });
				return port;
			} catch (error) {
				// 端口不可用，继续尝试下一个
				continue;
			}
		}
		throw new Error('无法找到可用端口');
	}

	async testConnection(url?: string): Promise<boolean> {
		try {
			const testUrl = url || this.settings.serviceUrl;
			await axios.get(`${testUrl}/api/service/status`, { timeout: 5000 });
			return true;
		} catch (error) {
			return false;
		}
	}
}