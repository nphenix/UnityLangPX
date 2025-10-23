import { App, Modal, Notice } from 'obsidian';

export class ProgressModal extends Modal {
	private progressEl!: HTMLElement;
	private statusEl!: HTMLElement;
	private progressBarEl!: HTMLElement;
	private progressTextEl!: HTMLElement;
	private cancelButton!: HTMLElement;
	private isCancelled: boolean = false;

	constructor(app: App) {
		super(app);
	}

	onOpen() {
		const { contentEl } = this;
		contentEl.empty();

		// 创建模态框标题
		contentEl.createEl('h2', { text: 'UnityLangPX翻译进度' });

		// 创建状态文本
		this.statusEl = contentEl.createEl('p', { 
			text: '准备翻译...',
			cls: 'translation-status'
		});

		// 创建进度条容器
		const progressContainer = contentEl.createDiv('progress-container');
		progressContainer.style.margin = '20px 0';

		// 创建进度条
		this.progressBarEl = progressContainer.createDiv('progress-bar');
		this.progressBarEl.style.width = '100%';
		this.progressBarEl.style.height = '10px';
		this.progressBarEl.style.backgroundColor = '#e0e0e0';
		this.progressBarEl.style.borderRadius = '5px';
		this.progressBarEl.style.overflow = 'hidden';

		// 创建进度条填充
		const progressFill = this.progressBarEl.createDiv('progress-fill');
		progressFill.style.width = '0%';
		progressFill.style.height = '100%';
		progressFill.style.backgroundColor = '#007bff';
		progressFill.style.transition = 'width 0.3s ease';

		// 创建进度文本
		this.progressTextEl = contentEl.createEl('p', { 
			text: '0%',
			cls: 'progress-text'
		});
		this.progressTextEl.style.textAlign = 'center';
		this.progressTextEl.style.marginTop = '10px';

		// 创建详细信息容器
		this.progressEl = contentEl.createDiv('progress-details');
		this.progressEl.style.marginTop = '15px';
		this.progressEl.style.fontSize = '14px';
		this.progressEl.style.color = '#666';

		// 创建取消按钮
		const buttonContainer = contentEl.createDiv('button-container');
		buttonContainer.style.display = 'flex';
		buttonContainer.style.justifyContent = 'center';
		buttonContainer.style.marginTop = '20px';

		this.cancelButton = buttonContainer.createEl('button', { 
			text: '取消翻译',
			cls: 'mod-cancel'
		});
		this.cancelButton.addEventListener('click', () => {
			this.cancel();
		});
	}

	updateStatus(status: string) {
		if (this.statusEl) {
			this.statusEl.textContent = status;
		}
	}

	updateProgress(percent: number, details?: string) {
		if (this.progressBarEl) {
			const progressFill = this.progressBarEl.querySelector('.progress-fill') as HTMLElement;
			if (progressFill) {
				progressFill.style.width = `${percent}%`;
			}
		}

		if (this.progressTextEl) {
			this.progressTextEl.textContent = `${Math.round(percent)}%`;
		}

		if (details && this.progressEl) {
			this.progressEl.textContent = details;
		}
	}

	addDetail(detail: string) {
		if (this.progressEl) {
			const detailEl = this.progressEl.createEl('div', { 
				text: detail,
				cls: 'progress-detail'
			});
			detailEl.style.marginTop = '5px';
			
			// 保持最多5条详细信息
			const details = this.progressEl.querySelectorAll('.progress-detail');
			if (details.length > 5) {
				details[0].remove();
			}
		}
	}

	setError(error: string) {
		if (this.statusEl) {
			this.statusEl.textContent = '翻译失败';
			this.statusEl.style.color = 'red';
		}

		if (this.progressEl) {
			this.progressEl.textContent = `错误: ${error}`;
			this.progressEl.style.color = 'red';
		}

		if (this.cancelButton) {
			this.cancelButton.textContent = '关闭';
			this.cancelButton.removeEventListener('click', this.cancel);
			this.cancelButton.addEventListener('click', () => {
				this.close();
			});
		}
	}

	setComplete(message?: string) {
		if (this.statusEl) {
			this.statusEl.textContent = message || '翻译完成';
			this.statusEl.style.color = 'green';
		}

		if (this.progressBarEl) {
			const progressFill = this.progressBarEl.querySelector('.progress-fill') as HTMLElement;
			if (progressFill) {
				progressFill.style.width = '100%';
				progressFill.style.backgroundColor = 'green';
			}
		}

		if (this.progressTextEl) {
			this.progressTextEl.textContent = '100%';
		}

		if (this.cancelButton) {
			this.cancelButton.textContent = '关闭';
			this.cancelButton.removeEventListener('click', this.cancel);
			this.cancelButton.addEventListener('click', () => {
				this.close();
			});
		}
	}

	cancel() {
		this.isCancelled = true;
		if (this.statusEl) {
			this.statusEl.textContent = '正在取消翻译...';
			this.statusEl.style.color = 'orange';
		}

		if (this.cancelButton) {
			this.cancelButton.textContent = '关闭';
			(this.cancelButton as HTMLButtonElement).disabled = true;
		}

		// 触发取消事件
		this.app.workspace.trigger('unitylangpx:translation-cancelled');
	}

	isTranslationCancelled(): boolean {
		return this.isCancelled;
	}

	onClose() {
		const { contentEl } = this;
		contentEl.empty();
	}
}