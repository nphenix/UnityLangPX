import { App, Plugin, PluginSettingTab, Setting, Notice, TFile } from 'obsidian';
import { UnityLangPXSettings, DEFAULT_SETTINGS } from './settings';
import { TranslationAPI } from './api/client';
import { TranslationModal } from './ui/modal';
import { ProgressModal } from './ui/progress';
import { HistoryModal } from './ui/history';

export default class UnityLangPXPlugin extends Plugin {
	settings!: UnityLangPXSettings;
	api!: TranslationAPI;

	async onload() {
		await this.loadSettings();

		// 初始化API客户端
		this.api = new TranslationAPI(this.settings);

		// 添加设置选项卡
		this.addSettingTab(new UnityLangPXSettingTab(this.app, this));

		// 注册文件右键菜单
		this.registerEvent(
			this.app.workspace.on('file-menu', (menu, file) => {
				if (file instanceof TFile && file.extension === 'md') {
					menu.addItem((item) => {
						item.setTitle('UnityLangPX翻译')
							.setIcon('languages')
							.onClick(async () => {
								await this.translateFile(file);
							});
					});
				}
			})
		);

		// 注册文件浏览器右键菜单（支持多选）
		this.registerEvent(
			this.app.workspace.on('files-menu', (menu, files) => {
				const markdownFiles = files.filter(file =>
					file instanceof TFile && file.extension === 'md'
				);
				
				if (markdownFiles.length > 0) {
					menu.addItem((item) => {
						item.setTitle('UnityLangPX翻译')
							.setIcon('languages')
							.onClick(async () => {
								if (markdownFiles.length === 1) {
									await this.translateFile(markdownFiles[0] as TFile);
								} else {
									await this.translateBatchFiles(markdownFiles as TFile[]);
								}
							});
					});
				}
			})
		);

		// 注册命令
		this.addCommand({
			id: 'translate-current-file',
			name: '翻译当前文件',
			editorCallback: (editor, view) => {
				const file = view.file;
				if (file) {
					this.translateFile(file);
				}
			}
		});

		this.addCommand({
			id: 'show-translation-history',
			name: '显示翻译历史',
			callback: () => {
				this.showTranslationHistory();
			}
		});

		// 启动时检查服务状态
		this.checkServiceStatus();
	}

	onunload() {
		// 插件卸载时的清理工作
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	async checkServiceStatus() {
		try {
			const status = await this.api.checkServiceStatus();
			if (!status.running) {
				new Notice('UnityLangPX翻译服务未运行，请启动服务', 5000);
			}
		} catch (error) {
			console.error('检查服务状态失败:', error);
			new Notice('无法连接到UnityLangPX翻译服务', 5000);
		}
	}

	async translateFile(file: TFile) {
		try {
			console.log('开始翻译文件:', file.path);
			
			// 检查服务状态
			console.log('检查服务状态...');
			const status = await this.api.checkServiceStatus();
			console.log('服务状态:', status);
			
			if (!status.running) {
				console.error('翻译服务未运行');
				new Notice('翻译服务未运行，请先启动服务', 3000);
				return;
			}

			console.log('服务正在运行，显示翻译选项对话框');

			// 显示翻译选项对话框
			const modal = new TranslationModal(
				this.app,
				this.settings,
				async (options) => {
					console.log('翻译选项:', options);
					
					// 开始翻译
					const progressModal = new ProgressModal(this.app);
					progressModal.open();

					try {
						console.log('读取文件内容...');
						const content = await this.app.vault.read(file);
						console.log('文件内容长度:', content.length);
						
						console.log('发送翻译请求...');
						const result = await this.api.translateFile({
							file_path: file.path,
							content: content,
							...options
						});

						console.log('翻译结果:', result);
						progressModal.close();

						if (result.success) {
							// 处理翻译结果
							await this.handleTranslationResult(file, result, options);
							new Notice(`翻译完成: ${file.name}`, 3000);
						} else {
							console.error('翻译失败:', result.error);
							new Notice(`翻译失败: ${result.error}`, 5000);
						}
					} catch (error) {
						progressModal.close();
						console.error('翻译失败:', error);
						const errorMessage = error instanceof Error ? error.message : String(error);
						new Notice(`翻译失败: ${errorMessage}`, 5000);
					}
				}
			);
			modal.open();
		} catch (error) {
			console.error('翻译文件失败:', error);
			const errorMessage = error instanceof Error ? error.message : String(error);
			new Notice(`翻译失败: ${errorMessage}`, 5000);
		}
	}

	async handleTranslationResult(file: TFile, result: any, options: any) {
		const { translated_content, output_path } = result;
		
		if (options.output_mode === 'overwrite') {
			// 覆盖原文件
			await this.app.vault.modify(file, translated_content);
		} else {
			// 创建新文件
			const newPath = options.output_mode === 'suffix' 
				? file.path.replace(/\.md$/, `_zh.md`)
				: output_path;
			
			const newFile = this.app.vault.getAbstractFileByPath(newPath);
			if (newFile) {
				await this.app.vault.modify(newFile as TFile, translated_content);
			} else {
				await this.app.vault.create(newPath, translated_content);
			}
		}

		// 保存到历史记录
		await this.saveToHistory(file, result, options);
	}

	async saveToHistory(file: TFile, result: any, options: any) {
		const history = this.settings.translationHistory || [];
		const entry = {
			id: this.generateId(),
			source_file: file.path,
			source_language: options.source_language,
			target_language: options.target_language,
			timestamp: new Date().toISOString(),
			duration: result.duration,
			chars_translated: result.chars_translated
		};

		history.unshift(entry);
		
		// 限制历史记录数量
		if (history.length > 100) {
			history.splice(100);
		}

		this.settings.translationHistory = history;
		await this.saveSettings();
	}

	async translateBatchFiles(files: TFile[]) {
		try {
			// 检查服务状态
			const status = await this.api.checkServiceStatus();
			if (!status.running) {
				new Notice('翻译服务未运行，请先启动服务', 3000);
				return;
			}

			// 显示翻译选项对话框
			const modal = new TranslationModal(
				this.app,
				this.settings,
				async (options) => {
					// 开始批量翻译
					const progressModal = new ProgressModal(this.app);
					progressModal.open();

					try {
						const filePaths = files.map(file => file.path);
						const result = await this.api.translateBatch(
							filePaths,
							'', // 输出目录，使用默认
							options.source_language,
							options.target_language
						);

						progressModal.close();

						if (result.success) {
							// 处理翻译结果
							await this.handleBatchTranslationResult(files, result, options);
							new Notice(`批量翻译完成: ${result.success_count}/${result.total_files} 文件`, 3000);
						} else {
							new Notice(`批量翻译失败: ${result.error}`, 5000);
						}
					} catch (error) {
						progressModal.close();
						console.error('批量翻译失败:', error);
						const errorMessage = error instanceof Error ? error.message : String(error);
						new Notice(`批量翻译失败: ${errorMessage}`, 5000);
					}
				}
			);
			modal.open();
		} catch (error) {
			console.error('批量翻译文件失败:', error);
			const errorMessage = error instanceof Error ? error.message : String(error);
			new Notice(`批量翻译失败: ${errorMessage}`, 5000);
		}
	}

	async handleBatchTranslationResult(files: TFile[], result: any, options: any) {
		// 处理批量翻译结果
		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			const fileResult = result.results[i];
			
			if (fileResult.success) {
				// 这里简化处理，实际应该读取翻译后的内容并更新文件
				// 由于API限制，我们只保存到历史记录
				await this.saveToHistory(file, {
					success: true,
					duration: 0,
					chars_translated: 0
				}, options);
			}
		}
	}

	showTranslationHistory() {
		const historyModal = new HistoryModal(this.app, this.settings);
		historyModal.open();
	}

	generateId(): string {
		return Date.now().toString(36) + Math.random().toString(36).substr(2);
	}
}

class UnityLangPXSettingTab extends PluginSettingTab {
	plugin: UnityLangPXPlugin;

	constructor(app: App, plugin: UnityLangPXPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		containerEl.createEl('h2', { text: 'UnityLangPX翻译设置' });

		// 服务设置
		containerEl.createEl('h3', { text: '服务设置' });

		new Setting(containerEl)
			.setName('服务地址')
			.setDesc('UnityLangPX翻译服务的地址')
			.addText(text => text
				.setPlaceholder('http://localhost:8000')
				.setValue(this.plugin.settings.serviceUrl)
				.onChange(async (value) => {
					this.plugin.settings.serviceUrl = value;
					await this.plugin.saveSettings();
					this.plugin.api.updateSettings(this.plugin.settings);
				}));

		new Setting(containerEl)
			.setName('自动检测服务')
			.setDesc('启动时自动检测并尝试启动翻译服务')
			.addToggle(toggle => toggle
				.setValue(this.plugin.settings.autoDetectService)
				.onChange(async (value) => {
					this.plugin.settings.autoDetectService = value;
					await this.plugin.saveSettings();
				}));

		// 翻译设置
		containerEl.createEl('h3', { text: '翻译设置' });

		new Setting(containerEl)
			.setName('源语言')
			.setDesc('默认的源语言')
			.addDropdown(dropdown => dropdown
				.addOption('en', '英文')
				.addOption('zh', '中文')
				.setValue(this.plugin.settings.sourceLanguage)
				.onChange(async (value) => {
					this.plugin.settings.sourceLanguage = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('目标语言')
			.setDesc('默认的目标语言')
			.addDropdown(dropdown => dropdown
				.addOption('en', '英文')
				.addOption('zh', '中文')
				.setValue(this.plugin.settings.targetLanguage)
				.onChange(async (value) => {
					this.plugin.settings.targetLanguage = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('默认文件处理方式')
			.setDesc('翻译完成后的文件处理方式')
			.addDropdown(dropdown => dropdown
				.addOption('suffix', '添加语言后缀')
				.addOption('overwrite', '覆盖原文件')
				.addOption('custom', '自定义路径')
				.setValue(this.plugin.settings.defaultOutputMode)
				.onChange(async (value) => {
					this.plugin.settings.defaultOutputMode = value as 'suffix' | 'overwrite' | 'custom';
					await this.plugin.saveSettings();
				}));

		// 服务管理
		containerEl.createEl('h3', { text: '服务管理' });

		const serviceStatusDiv = containerEl.createDiv();
		serviceStatusDiv.createEl('p', { text: '服务状态: 检查中...' });

		// 检查服务状态按钮
		new Setting(containerEl)
			.setName('检查服务状态')
			.setDesc('检查UnityLangPX翻译服务是否正在运行')
			.addButton(button => button
				.setButtonText('检查状态')
				.onClick(async () => {
					const statusParagraph = serviceStatusDiv.querySelector('p');
					if (statusParagraph) {
						statusParagraph.textContent = '服务状态: 检查中...';
						try {
							const status = await this.plugin.api.checkServiceStatus();
							if (status.running) {
								statusParagraph.textContent = `服务状态: 运行中 (端口: ${status.port})`;
								statusParagraph.setAttribute('style', 'color: green');
							} else {
								statusParagraph.textContent = '服务状态: 未运行';
								statusParagraph.setAttribute('style', 'color: red');
							}
						} catch (error) {
							statusParagraph.textContent = '服务状态: 连接失败';
							statusParagraph.setAttribute('style', 'color: red');
						}
					}
				}));

		new Setting(containerEl)
			.setName('启动服务')
			.setDesc('尝试启动UnityLangPX翻译服务')
			.addButton(button => button
				.setButtonText('启动服务')
				.onClick(async () => {
					try {
						const result = await this.plugin.api.startService();
						if (result.success) {
							new Notice(`服务启动成功 (端口: ${result.port})`, 3000);
						} else {
							new Notice(`服务启动失败: ${result.error}`, 5000);
						}
					} catch (error) {
						const errorMessage = error instanceof Error ? error.message : String(error);
						new Notice(`启动服务失败: ${errorMessage}`, 5000);
					}
				}));

		// 高级选项
		containerEl.createEl('h3', { text: '高级选项' });

		new Setting(containerEl)
			.setName('清空翻译历史')
			.setDesc('清空所有翻译历史记录')
			.addButton(button => button
				.setButtonText('清空历史')
				.onClick(async () => {
					this.plugin.settings.translationHistory = [];
					await this.plugin.saveSettings();
					new Notice('翻译历史已清空', 3000);
				}));

		new Setting(containerEl)
			.setName('导出设置')
			.setDesc('导出当前插件设置到文件')
			.addButton(button => button
				.setButtonText('导出设置')
				.onClick(async () => {
					await this.exportSettings();
				}));

		new Setting(containerEl)
			.setName('导入设置')
			.setDesc('从文件导入插件设置')
			.addButton(button => button
				.setButtonText('导入设置')
				.onClick(async () => {
					await this.importSettings();
				}));

		new Setting(containerEl)
			.setName('重置设置')
			.setDesc('重置所有设置为默认值')
			.addButton(button => button
				.setButtonText('重置设置')
				.onClick(async () => {
					if (confirm('确定要重置所有设置吗？此操作不可撤销。')) {
						await this.resetSettings();
					}
				}));
	}

	async exportSettings() {
		try {
			const settings = this.plugin.settings;
			const settingsJson = JSON.stringify(settings, null, 2);
			const blob = new Blob([settingsJson], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			
			const a = document.createElement('a');
			a.href = url;
			a.download = 'unitylangpx-settings.json';
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			
			new Notice('设置已导出', 3000);
		} catch (error) {
			console.error('导出设置失败:', error);
			new Notice('导出设置失败', 3000);
		}
	}

	async importSettings() {
		try {
			const input = document.createElement('input');
			input.type = 'file';
			input.accept = '.json';
			
			input.onchange = async (event) => {
				const file = (event.target as HTMLInputElement).files?.[0];
				if (!file) return;
				
				try {
					const text = await file.text();
					const settings = JSON.parse(text);
					
					// 验证设置格式
					if (this.validateSettings(settings)) {
						this.plugin.settings = { ...DEFAULT_SETTINGS, ...settings };
						await this.plugin.saveSettings();
						new Notice('设置已导入', 3000);
						this.display(); // 刷新设置界面
					} else {
						new Notice('无效的设置文件格式', 3000);
					}
				} catch (error) {
					console.error('导入设置失败:', error);
					new Notice('导入设置失败', 3000);
				}
			};
			
			input.click();
		} catch (error) {
			console.error('导入设置失败:', error);
			new Notice('导入设置失败', 3000);
		}
	}

	validateSettings(settings: any): boolean {
		// 基本验证
		if (!settings || typeof settings !== 'object') {
			return false;
		}
		
		// 检查必需的字段
		const requiredFields = ['serviceUrl', 'sourceLanguage', 'targetLanguage'];
		for (const field of requiredFields) {
			if (!(field in settings)) {
				return false;
			}
		}
		
		return true;
	}

	async resetSettings() {
		try {
			this.plugin.settings = { ...DEFAULT_SETTINGS };
			await this.plugin.saveSettings();
			new Notice('设置已重置', 3000);
			this.display(); // 刷新设置界面
		} catch (error) {
			console.error('重置设置失败:', error);
			new Notice('重置设置失败', 3000);
		}
	}
}