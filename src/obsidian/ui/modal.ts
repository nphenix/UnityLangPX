import { App, Modal, Setting, Notice } from 'obsidian';
import { UnityLangPXSettings, DEFAULT_SETTINGS } from '../settings';
import { TranslationOptions } from '../api/types';

export class TranslationModal extends Modal {
	private settings: UnityLangPXSettings;
	private options: TranslationOptions;
	private onSubmit: (options: TranslationOptions) => void;

	constructor(app: App, settings: UnityLangPXSettings, onSubmit: (options: TranslationOptions) => void) {
		super(app);
		this.settings = settings;
		this.onSubmit = onSubmit;
		
		// 初始化选项
		this.options = {
			source_language: settings.sourceLanguage,
			target_language: settings.targetLanguage,
			output_mode: settings.defaultOutputMode,
			overwrite: false
		};
	}

	onOpen() {
		const { contentEl } = this;
		contentEl.empty();

		contentEl.createEl('h2', { text: 'UnityLangPX翻译选项' });

		// 源语言设置
		new Setting(contentEl)
			.setName('源语言')
			.setDesc('选择要翻译的源语言')
			.addDropdown(dropdown => {
				dropdown
					.addOption('en', '英文')
					.addOption('zh', '中文')
					.setValue(this.options.source_language)
					.onChange(async (value) => {
						this.options.source_language = value;
					});
			});

		// 目标语言设置
		new Setting(contentEl)
			.setName('目标语言')
			.setDesc('选择翻译的目标语言')
			.addDropdown(dropdown => {
				dropdown
					.addOption('en', '英文')
					.addOption('zh', '中文')
					.setValue(this.options.target_language)
					.onChange(async (value) => {
						this.options.target_language = value;
					});
			});

		// 输出模式设置
		new Setting(contentEl)
			.setName('输出模式')
			.setDesc('选择翻译结果的输出方式')
			.addDropdown(dropdown => {
				dropdown
					.addOption('suffix', '添加语言后缀 (例如: file_zh.md)')
					.addOption('overwrite', '覆盖原文件')
					.addOption('custom', '自定义路径')
					.setValue(this.options.output_mode)
					.onChange(async (value) => {
						this.options.output_mode = value as 'suffix' | 'overwrite' | 'custom';
					});
			});

		// 自定义路径设置（仅在输出模式为custom时显示）
		const customPathContainer = contentEl.createDiv();
		customPathContainer.style.display = this.options.output_mode === 'custom' ? 'block' : 'none';
		
		const customPathSetting = new Setting(customPathContainer)
			.setName('自定义输出路径')
			.setDesc('指定翻译文件的输出路径（相对于库根目录）')
			.addText(text => {
				text
					.setPlaceholder('translated/file.md')
					.setValue(this.options.output_path || '')
					.onChange(async (value) => {
						this.options.output_path = value;
					});
			});

		// 监听输出模式变化，显示/隐藏自定义路径设置
		const outputModeDropdown = contentEl.querySelector('.dropdown-container:nth-child(4) select') as HTMLSelectElement;
		if (outputModeDropdown) {
			outputModeDropdown.addEventListener('change', () => {
				customPathContainer.style.display = 
					outputModeDropdown.value === 'custom' ? 'block' : 'none';
			});
		}

		// 高级选项
		const advancedContainer = contentEl.createDiv('advanced-options');
		advancedContainer.createEl('h3', { text: '高级选项' });

		new Setting(advancedContainer)
			.setName('覆盖已存在文件')
			.setDesc('如果输出文件已存在，是否覆盖')
			.addToggle(toggle => {
				toggle
					.setValue(this.options.overwrite || false)
					.onChange(async (value) => {
						this.options.overwrite = value;
					});
			});

		// 按钮
		const buttonContainer = contentEl.createDiv('button-container');
		buttonContainer.style.display = 'flex';
		buttonContainer.style.justifyContent = 'flex-end';
		buttonContainer.style.gap = '10px';
		buttonContainer.style.marginTop = '20px';

		const cancelButton = buttonContainer.createEl('button', { text: '取消' });
		cancelButton.className = 'mod-cta';
		cancelButton.addEventListener('click', () => {
			this.close();
		});

		const translateButton = buttonContainer.createEl('button', { text: '开始翻译' });
		translateButton.className = 'mod-cta';
		translateButton.style.backgroundColor = '#007bff';
		translateButton.style.color = 'white';
		translateButton.addEventListener('click', () => {
			// 验证选项
			if (!this.options.source_language || !this.options.target_language) {
				new Notice('请选择源语言和目标语言', 3000);
				return;
			}

			if (this.options.source_language === this.options.target_language) {
				new Notice('源语言和目标语言不能相同', 3000);
				return;
			}

			if (this.options.output_mode === 'custom' && !this.options.output_path) {
				new Notice('自定义输出模式下必须指定输出路径', 3000);
				return;
			}

			// 提交选项
			this.onSubmit(this.options);
			this.close();
		});
	}

	onClose() {
		const { contentEl } = this;
		contentEl.empty();
	}
}