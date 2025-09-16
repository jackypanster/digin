/**
 * Digin Web 界面交互逻辑
 * 简单的单页应用，展示 digest.json 分析结果
 */

class DiginViewer {
    constructor() {
        this.currentPath = '/';
        this.projectInfo = null;
        this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        await this.loadProjectInfo();
        await this.loadDigest('/');
        this.setupEventListeners();
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 刷新按钮
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshCurrentView();
            });
        }
    }

    /**
     * 加载项目基本信息
     */
    async loadProjectInfo() {
        try {
            const response = await fetch('/api/info');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.projectInfo = await response.json();
            document.getElementById('project-name').textContent = this.projectInfo.target_name;
        } catch (error) {
            console.error('加载项目信息失败:', error);
            this.showError('无法加载项目信息：' + error.message);
        }
    }

    /**
     * 加载指定路径的 digest 数据
     */
    async loadDigest(path) {
        this.showLoading();

        try {
            const response = await fetch(`/api/digest?path=${encodeURIComponent(path)}`);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const digest = await response.json();
            this.currentPath = path;
            this.renderDigest(digest);
            this.updateDirectoryTree(path);

        } catch (error) {
            console.error('加载 digest 失败:', error);
            this.showError('加载失败：' + error.message);
        }
    }

    /**
     * 渲染 digest 数据到界面
     */
    renderDigest(digest) {
        this.hideLoading();
        this.showContent();

        // 基本信息
        this.updateElement('project-kind', digest.kind || 'unknown');
        this.updateElement('project-path', digest.path || this.currentPath);
        this.updateElement('project-summary', digest.summary || '暂无摘要信息');

        // 置信度
        this.updateConfidence(digest.confidence);

        // 功能能力
        this.renderCapabilities(digest.capabilities || []);

        // 接口信息
        this.renderInterfaces(digest.public_interfaces);

        // 依赖关系
        this.renderDependencies(digest.dependencies);

        // 风险提示
        this.renderRisks(digest.risks);
    }

    /**
     * 更新置信度显示
     */
    updateConfidence(confidence) {
        const badge = document.getElementById('confidence-badge');
        if (badge && confidence !== undefined) {
            badge.textContent = `置信度: ${confidence}%`;

            // 根据置信度设置样式
            badge.className = 'confidence-badge';
            if (confidence >= 80) {
                badge.classList.add('high');
            } else if (confidence >= 60) {
                badge.classList.add('medium');
            } else {
                badge.classList.add('low');
            }
        }
    }

    /**
     * 渲染功能能力列表
     */
    renderCapabilities(capabilities) {
        const list = document.getElementById('capabilities-list');
        if (!list) return;

        list.innerHTML = '';

        if (capabilities.length === 0) {
            list.innerHTML = '<li style="color: #64748b;">暂无功能信息</li>';
            return;
        }

        capabilities.forEach(capability => {
            const li = document.createElement('li');
            li.textContent = capability;
            list.appendChild(li);
        });
    }

    /**
     * 渲染接口信息
     */
    renderInterfaces(interfaces) {
        const card = document.getElementById('interfaces-card');
        const content = document.getElementById('interfaces-content');

        if (!interfaces || Object.keys(interfaces).length === 0) {
            card.style.display = 'none';
            return;
        }

        card.style.display = 'block';
        content.innerHTML = '';

        // HTTP 接口
        if (interfaces.http && interfaces.http.length > 0) {
            const section = this.createInterfaceSection('HTTP API', interfaces.http, item =>
                `${item.method} ${item.path} → ${item.handler || 'Unknown'}`
            );
            content.appendChild(section);
        }

        // RPC 接口
        if (interfaces.rpc && interfaces.rpc.length > 0) {
            const section = this.createInterfaceSection('RPC', interfaces.rpc, item =>
                `${item.service}.${item.method}`
            );
            content.appendChild(section);
        }

        // CLI 接口
        if (interfaces.cli && interfaces.cli.length > 0) {
            const section = this.createInterfaceSection('命令行', interfaces.cli, item =>
                item.cmd || item
            );
            content.appendChild(section);
        }

        // API 接口
        if (interfaces.api && interfaces.api.length > 0) {
            const section = this.createInterfaceSection('API', interfaces.api, item =>
                `${item.function}${item.signature ? ': ' + item.signature : ''}`
            );
            content.appendChild(section);
        }
    }

    /**
     * 创建接口部分
     */
    createInterfaceSection(title, items, formatter) {
        const section = document.createElement('div');
        section.className = 'interface-section';

        const heading = document.createElement('h4');
        heading.textContent = title;
        section.appendChild(heading);

        const list = document.createElement('ul');
        list.className = 'interface-list';

        items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'interface-item';
            li.textContent = formatter(item);
            list.appendChild(li);
        });

        section.appendChild(list);
        return section;
    }

    /**
     * 渲染依赖关系
     */
    renderDependencies(dependencies) {
        const card = document.getElementById('dependencies-card');
        const content = document.getElementById('dependencies-content');

        if (!dependencies || ((!dependencies.external || dependencies.external.length === 0) &&
                             (!dependencies.internal || dependencies.internal.length === 0))) {
            card.style.display = 'none';
            return;
        }

        card.style.display = 'block';
        content.innerHTML = '';

        // 外部依赖
        if (dependencies.external && dependencies.external.length > 0) {
            const section = this.createDependencySection('外部依赖', dependencies.external);
            content.appendChild(section);
        }

        // 内部依赖
        if (dependencies.internal && dependencies.internal.length > 0) {
            const section = this.createDependencySection('内部依赖', dependencies.internal);
            content.appendChild(section);
        }
    }

    /**
     * 创建依赖部分
     */
    createDependencySection(title, dependencies) {
        const section = document.createElement('div');
        section.className = 'dependency-section';

        const heading = document.createElement('h4');
        heading.textContent = title;
        section.appendChild(heading);

        const list = document.createElement('ul');
        list.className = 'dependency-list';

        dependencies.forEach(dep => {
            const li = document.createElement('li');
            li.className = 'dependency-item';
            li.textContent = dep;
            list.appendChild(li);
        });

        section.appendChild(list);
        return section;
    }

    /**
     * 渲染风险提示
     */
    renderRisks(risks) {
        const card = document.getElementById('risks-card');
        const list = document.getElementById('risks-list');

        if (!risks || risks.length === 0) {
            card.style.display = 'none';
            return;
        }

        card.style.display = 'block';
        list.innerHTML = '';

        risks.forEach(risk => {
            const li = document.createElement('li');
            li.textContent = risk;
            list.appendChild(li);
        });
    }

    /**
     * 更新目录树（简化版，暂时只显示当前路径）
     */
    updateDirectoryTree(currentPath) {
        const tree = document.getElementById('directory-tree');
        if (!tree) return;

        // 简化版：只显示当前选中的路径
        tree.innerHTML = `
            <div class="tree-item active" onclick="viewer.loadDigest('/')">
                📁 ${this.projectInfo?.target_name || '项目根目录'}
                ${currentPath !== '/' ? ` → ${currentPath}` : ''}
            </div>
        `;
    }

    /**
     * 刷新当前视图
     */
    async refreshCurrentView() {
        await this.loadDigest(this.currentPath);
    }

    /**
     * 显示加载状态
     */
    showLoading() {
        document.getElementById('loading-state').style.display = 'flex';
        document.getElementById('error-state').style.display = 'none';
        document.getElementById('content-area').style.display = 'none';
    }

    /**
     * 隐藏加载状态
     */
    hideLoading() {
        document.getElementById('loading-state').style.display = 'none';
    }

    /**
     * 显示内容区域
     */
    showContent() {
        document.getElementById('content-area').style.display = 'block';
        document.getElementById('error-state').style.display = 'none';
    }

    /**
     * 显示错误信息
     */
    showError(message) {
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('content-area').style.display = 'none';
        document.getElementById('error-state').style.display = 'block';
        document.getElementById('error-message').textContent = message;
    }

    /**
     * 更新元素内容
     */
    updateElement(id, content) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = content;
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.viewer = new DiginViewer();
});