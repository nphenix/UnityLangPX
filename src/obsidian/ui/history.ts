import { App, Modal, Setting, Notice } from 'obsidian';
import { UnityLangPXSettings, TranslationHistoryEntry } from '../settings';

export class HistoryModal extends Modal {
	private settings: UnityLangPXSettings;
	
	constructor(app: App, settings: UnityLangPXSettings) {
		super(app);
		this.settings = settings;
	}

	onOpen() {
		const { contentEl } = this;
		contentEl.empty();

		contentEl.createEl('h2', { text: 'UnityLangPX翻译历史' });

		// 创建工具栏
		const toolbar = contentEl.createDiv('history-toolbar');
		toolbar.style.display = 'flex';
		toolbar.style.justifyContent = 'space-between';
		toolbar.style.alignItems = 'center';
		toolbar.style.marginBottom = '20px';

		// 刷新按钮
		const refreshButton = toolbar.createEl('button', { 
			text: '刷新',
			cls: 'mod-cta'
		});
		refreshButton.style.marginRight = '10px';
		refreshButton.addEventListener('click', () => {
			this.refreshHistory();
		});

		// 清空历史按钮
		const clearButton = toolbar.createEl('button', { 
			text: '清空历史',
			cls: 'mod-warning'
		});
		clearButton.addEventListener('click', () => {
			this.clearHistory();
		});

		// 关闭按钮
		const closeButton = toolbar.createEl('button', { 
			text: '关闭',
			cls: 'mod-cancel'
		});
		closeButton.addEventListener('click', () => {
			this.close();
		});

		// 创建历史记录列表
		const historyContainer = contentEl.createDiv('history-container');
		historyContainer.style.maxHeight = '400px';
		historyContainer.style.overflowY = 'auto';
		historyContainer.style.border = '1px solid #ccc';
		historyContainer.style.borderRadius = '5px';
		historyContainer.style.padding = '10px';

		this.displayHistory(historyContainer);
	}

	displayHistory(container: HTMLElement) {
		container.empty();
		
		const history = this.settings.translationHistory || [];
		
		if (history.length === 0) {
			const emptyEl = container.createEl('p', {
				text: '暂无翻译历史记录',
				cls: 'history-empty'
			});
			emptyEl.style.textAlign = 'center';
			emptyEl.style.color = '#666';
			return;
		}

		// 创建表格
		const table = container.createEl('table', { 
			cls: 'history-table'
		});
		table.style.width = '100%';
		table.style.borderCollapse = 'collapse';

		// 创建表头
		const thead = table.createEl('thead');
		const headerRow = thead.createEl('tr');
		
		const headers = ['文件名', '源语言', '目标语言', '时间', '字符数', '耗时'];
		headers.forEach(headerText => {
			const th = headerRow.createEl('th', { text: headerText });
			th.style.padding = '8px';
			th.style.textAlign = 'left';
			th.style.borderBottom = '1px solid #ddd';
			th.style.backgroundColor = '#f5f5f5';
		});

		// 创建表体
		const tbody = table.createEl('tbody');
		
		history.forEach((entry, index) => {
			const row = tbody.createEl('tr');
			row.style.borderBottom = '1px solid #eee';
			
			// 文件名
			const fileCell = row.createEl('td');
			fileCell.textContent = entry.source_file;
			fileCell.style.padding = '8px';
			fileCell.style.maxWidth = '200px';
			fileCell.style.overflow = 'hidden';
			fileCell.style.textOverflow = 'ellipsis';
			fileCell.style.whiteSpace = 'nowrap';
			
			// 源语言
			const sourceLangCell = row.createEl('td');
			sourceLangCell.textContent = entry.source_language;
			sourceLangCell.style.padding = '8px';
			sourceLangCell.style.textAlign = 'center';
			
			// 目标语言
			const targetLangCell = row.createEl('td');
			targetLangCell.textContent = entry.target_language;
			targetLangCell.style.padding = '8px';
			targetLangCell.style.textAlign = 'center';
			
			// 时间
			const timeCell = row.createEl('td');
			const date = new Date(entry.timestamp);
			timeCell.textContent = date.toLocaleString();
			timeCell.style.padding = '8px';
			timeCell.style.fontSize = '12px';
			
			// 字符数
			const charsCell = row.createEl('td');
			charsCell.textContent = entry.chars_translated.toString();
			charsCell.style.padding = '8px';
			charsCell.style.textAlign = 'right';
			
			// 耗时
			const durationCell = row.createEl('td');
			durationCell.textContent = `${entry.duration.toFixed(2)}s`;
			durationCell.style.padding = '8px';
			durationCell.style.textAlign = 'right';
			
			// 添加悬停效果
			row.addEventListener('mouseenter', () => {
				row.style.backgroundColor = '#f5f5f5';
			});
			
			row.addEventListener('mouseleave', () => {
				row.style.backgroundColor = '';
			});
		});
	}

	refreshHistory() {
		const historyContainer = this.contentEl.querySelector('.history-container') as HTMLElement;
		if (historyContainer) {
			this.displayHistory(historyContainer);
			new Notice('历史记录已刷新', 2000);
		}
	}

	async clearHistory() {
		if (!confirm('确定要清空所有翻译历史记录吗？此操作不可撤销。')) {
			return;
		}

		try {
			this.settings.translationHistory = [];
			await this.saveSettings();
			
			const historyContainer = this.contentEl.querySelector('.history-container') as HTMLElement;
			if (historyContainer) {
				this.displayHistory(historyContainer);
			}
			
			new Notice('翻译历史已清空', 3000);
		} catch (error) {
			console.error('清空历史记录失败:', error);
			new Notice('清空历史记录失败', 3000);
		}
	}

	async saveSettings() {
		// 直接保存到插件数据
		try {
			// 获取插件实例
			const plugin = (this.app as any).plugins.plugins['unitylangpx-obsidian'];
			if (plugin && plugin.saveSettings) {
				plugin.settings = this.settings;
				await plugin.saveSettings();
			}
		} catch (error) {
			console.error('保存设置失败:', error);
		}
	}

	onClose() {
		const { contentEl } = this;
		contentEl.empty();
	}
}