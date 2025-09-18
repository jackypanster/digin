/**
 * Digin Web 界面交互逻辑
 * 简单的单页应用，展示 digest.json 分析结果
 */

class DiginViewer {
    constructor() {
        this.currentPath = '/';
        this.projectInfo = null;
        this.projectMap = null;
        this.isOnboardingMode = false;
        this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        await this.loadProjectInfo();
        await this.loadProjectMap();
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

        // 引导模式切换按钮
        const toggleOnboarding = document.getElementById('toggle-onboarding');
        if (toggleOnboarding) {
            toggleOnboarding.addEventListener('click', () => {
                this.toggleOnboardingMode();
            });
        }

        // 开始引导按钮
        const startOnboarding = document.getElementById('start-onboarding');
        if (startOnboarding) {
            startOnboarding.addEventListener('click', () => {
                this.startOnboardingPath();
            });
        }
    }

    /**
     * 加载项目地图数据
     */
    async loadProjectMap() {
        try {
            const response = await fetch('/api/project-map');
            if (!response.ok) {
                console.warn('项目地图加载失败，使用基础模式');
                return;
            }

            this.projectMap = await response.json();
            this.renderProjectTree();
            this.setupOnboardingCard();

        } catch (error) {
            console.error('加载项目地图失败:', error);
            // 降级到基础目录树模式
            this.renderBasicTree();
        }
    }

    /**
     * 渲染项目树结构
     */
    renderProjectTree() {
        if (!this.projectMap) return;

        const treeContainer = document.getElementById('directory-tree');
        if (!treeContainer) return;

        // 清空现有内容
        treeContainer.innerHTML = '';

        // 渲染树根节点
        const rootElement = this.createTreeNode(this.projectMap.tree, true);
        treeContainer.appendChild(rootElement);

        // 默认展开根节点
        this.expandNode(rootElement);
    }

    /**
     * 创建树节点元素
     */
    createTreeNode(node, isRoot = false) {
        const nodeElement = document.createElement('div');
        nodeElement.className = 'tree-node';
        nodeElement.dataset.path = node.path;

        // 添加特殊样式
        if (node.is_onboarding_path) {
            nodeElement.classList.add('onboarding-path');
        }
        if (node.is_recommended_reading) {
            nodeElement.classList.add('recommended-reading');
        }

        // 节点内容
        const nodeContent = document.createElement('div');
        nodeContent.className = 'tree-node-content';

        // 展开/收缩按钮（如果有子节点）
        if (node.children.length > 0) {
            const toggleBtn = document.createElement('span');
            toggleBtn.className = 'tree-toggle';
            toggleBtn.textContent = '▶';
            toggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleNode(nodeElement);
            });
            nodeContent.appendChild(toggleBtn);
        } else {
            const spacer = document.createElement('span');
            spacer.className = 'tree-spacer';
            nodeContent.appendChild(spacer);
        }

        // 节点图标
        const icon = document.createElement('span');
        icon.className = 'tree-icon';
        icon.textContent = this.getNodeIcon(node.kind);
        nodeContent.appendChild(icon);

        // 节点名称
        const name = document.createElement('span');
        name.className = 'tree-name';
        name.textContent = node.name;
        nodeContent.appendChild(name);

        // 重要性指示器
        if (node.is_onboarding_path) {
            const badge = document.createElement('span');
            badge.className = 'onboarding-badge';
            badge.textContent = '🚀';
            badge.title = '引导路径';
            nodeContent.appendChild(badge);
        }

        // 置信度指示器
        if (node.confidence > 0) {
            const confidence = document.createElement('span');
            confidence.className = 'confidence-indicator';
            confidence.textContent = `${node.confidence}%`;
            confidence.title = `置信度: ${node.confidence}%`;
            nodeContent.appendChild(confidence);
        }

        nodeElement.appendChild(nodeContent);

        // 点击事件
        nodeContent.addEventListener('click', () => {
            this.selectNode(node.path, nodeElement);
        });

        // 子节点容器
        if (node.children.length > 0) {
            const childrenContainer = document.createElement('div');
            childrenContainer.className = 'tree-children';

            node.children.forEach(child => {
                const childElement = this.createTreeNode(child);
                childrenContainer.appendChild(childElement);
            });

            nodeElement.appendChild(childrenContainer);
        }

        return nodeElement;
    }

    /**
     * 获取节点图标
     */
    getNodeIcon(kind) {
        const icons = {
            'service': '⚙️',
            'lib': '📚',
            'ui': '🎨',
            'infra': '🏗️',
            'config': '⚙️',
            'test': '🧪',
            'docs': '📄',
            'unknown': '📁'
        };
        return icons[kind] || '📁';
    }

    /**
     * 展开/收缩节点
     */
    toggleNode(nodeElement) {
        const toggle = nodeElement.querySelector('.tree-toggle');
        const children = nodeElement.querySelector('.tree-children');

        if (!toggle || !children) return;

        const isExpanded = children.style.display !== 'none';

        if (isExpanded) {
            children.style.display = 'none';
            toggle.textContent = '▶';
            nodeElement.classList.remove('expanded');
        } else {
            children.style.display = 'block';
            toggle.textContent = '▼';
            nodeElement.classList.add('expanded');
        }
    }

    /**
     * 展开节点
     */
    expandNode(nodeElement) {
        const toggle = nodeElement.querySelector('.tree-toggle');
        const children = nodeElement.querySelector('.tree-children');

        if (toggle && children) {
            children.style.display = 'block';
            toggle.textContent = '▼';
            nodeElement.classList.add('expanded');
        }
    }

    /**
     * 选择节点
     */
    selectNode(path, nodeElement) {
        // 移除所有节点的选中状态
        document.querySelectorAll('.tree-node').forEach(node => {
            node.classList.remove('selected');
        });

        // 添加当前节点的选中状态
        nodeElement.classList.add('selected');

        // 加载对应的 digest 数据
        this.loadDigest(path);
    }

    /**
     * 设置引导卡片
     */
    setupOnboardingCard() {
        if (!this.projectMap || !this.projectMap.onboarding_path) return;

        const card = document.getElementById('onboarding-card');
        if (!card) return;

        const onboarding = this.projectMap.onboarding_path;

        // 更新统计信息
        document.getElementById('onboarding-steps').textContent = `${onboarding.total_steps} 步`;
        document.getElementById('onboarding-time').textContent = onboarding.estimated_time;
        document.getElementById('onboarding-difficulty').textContent = this.getDifficultyText(onboarding.difficulty);

        // 显示卡片
        card.style.display = 'block';
    }

    /**
     * 获取难度描述
     */
    getDifficultyText(difficulty) {
        const texts = {
            'easy': '簡單',
            'medium': '中等',
            'hard': '困難'
        };
        return texts[difficulty] || '中等';
    }

    /**
     * 切换引导模式
     */
    toggleOnboardingMode() {
        this.isOnboardingMode = !this.isOnboardingMode;

        const toggleBtn = document.getElementById('toggle-onboarding');
        if (toggleBtn) {
            toggleBtn.textContent = this.isOnboardingMode ? '👁️‍🗨️' : '👁️';
        }

        // 更新树的显示样式
        this.updateTreeOnboardingHighlight();
    }

    /**
     * 更新树的引导高亮
     */
    updateTreeOnboardingHighlight() {
        const treeContainer = document.getElementById('directory-tree');
        if (!treeContainer) return;

        if (this.isOnboardingMode) {
            treeContainer.classList.add('onboarding-mode');
        } else {
            treeContainer.classList.remove('onboarding-mode');
        }
    }

    /**
     * 开始引导路径
     */
    startOnboardingPath() {
        if (!this.projectMap || !this.projectMap.onboarding_path.steps.length) return;

        this.isOnboardingMode = true;
        this.updateTreeOnboardingHighlight();

        // 跳转到第一个引导步骤
        const firstStep = this.projectMap.onboarding_path.steps[0];
        if (firstStep) {
            this.selectNodeByPath(firstStep.path);
        }
    }

    /**
     * 根据路径选择节点
     */
    selectNodeByPath(path) {
        const nodeElement = document.querySelector(`[data-path="${path}"]`);
        if (nodeElement) {
            this.selectNode(path, nodeElement);

            // 确保节点可见（展开父节点）
            this.expandParentNodes(nodeElement);

            // 滚动到节点
            nodeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    /**
     * 展开父节点
     */
    expandParentNodes(nodeElement) {
        let parent = nodeElement.parentElement;
        while (parent) {
            if (parent.classList.contains('tree-children')) {
                const parentNode = parent.parentElement;
                if (parentNode.classList.contains('tree-node')) {
                    this.expandNode(parentNode);
                }
            }
            parent = parent.parentElement;
        }
    }

    /**
     * 渲染基础目录树（降级模式）
     */
    renderBasicTree() {
        const treeContainer = document.getElementById('directory-tree');
        if (!treeContainer) return;

        treeContainer.innerHTML = '<div class="tree-fallback">📁 基础目录模式</div>';
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

        // 渲染敘述歡迎卡片（优先显示）
        this.renderNarrativeWelcome(digest.narrative);

        // 基本信息和摘要
        this.updateElement('project-kind', digest.kind || 'unknown');
        this.updateElement('project-path', digest.path || this.currentPath);
        this.renderSummarySection(digest);

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
     * 更新目录树选中状态（保留项目地图功能）
     */
    updateDirectoryTree(currentPath) {
        // 如果有项目地图，只更新选中状态，保留所有交互功能
        if (this.projectMap) {
            // selectNode已经处理了选中状态，这里无需重复操作
            return;
        }

        // 降级模式：没有项目地图时使用简单显示
        const tree = document.getElementById('directory-tree');
        if (!tree) return;

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
     * 渲染摘要部分（合并narrative和technical）
     */
    renderSummarySection(digest) {
        // 更新技术摘要
        this.updateElement('project-summary', digest.summary || '暂无摘要信息');

        // 显示narrative摘要（如果存在）
        const narrativeSummarySection = document.getElementById('narrative-summary-section');
        const narrativeSummaryText = document.getElementById('narrative-summary-text');

        if (digest.narrative && digest.narrative.summary) {
            if (narrativeSummaryText) {
                narrativeSummaryText.textContent = digest.narrative.summary;
            }
            if (narrativeSummarySection) {
                narrativeSummarySection.style.display = 'block';
            }
        } else {
            if (narrativeSummarySection) {
                narrativeSummarySection.style.display = 'none';
            }
        }
    }

    /**
     * 渲染敘述歡迎卡片
     */
    renderNarrativeWelcome(narrative) {
        const handshakeElement = document.getElementById('narrative-handshake-text');
        const nextStepsSection = document.getElementById('narrative-next-steps-section');
        const nextStepsText = document.getElementById('narrative-next-steps-text');

        if (!narrative) {
            // 如果没有 narrative 数据，显示默认信息
            if (handshakeElement) {
                handshakeElement.textContent = '歡迎探索這個項目！正在加載詳細信息...';
            }
            if (nextStepsSection) {
                nextStepsSection.style.display = 'none';
            }
            return;
        }

        // 显示 handshake
        if (handshakeElement && narrative.handshake) {
            handshakeElement.textContent = narrative.handshake;
        }

        // 显示 next_steps
        if (nextStepsText && narrative.next_steps) {
            nextStepsText.textContent = narrative.next_steps;
            if (nextStepsSection) {
                nextStepsSection.style.display = 'block';
            }
        } else if (nextStepsSection) {
            nextStepsSection.style.display = 'none';
        }
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