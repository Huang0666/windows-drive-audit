"""Conservative, local folder attribution. Rules propose actions and never execute them."""

import os


KEEP = '保留'
CHECK = '人工确认'
ARCHIVE = '备份后处理'
APP = '应用内清理或卸载'
SYSTEM = 'Windows 清理入口'
CLEAN = '可重建或旧残留'
RECYCLE = '确认后清空'
UNREAD = '权限或链接待核对'


def relative_to_drive(root, path):
    candidate = os.path.normpath(path)
    return candidate[len(root):] if candidate.casefold().startswith(root.casefold()) else ''


def build_rules(root, programs, packages, stores):
    rules = {'': ('磁盘根目录', 'Windows 目录结构', KEEP, '包含本盘的文件和目录。请进入下一层查看。')}

    def add(path, owner, action, reason, basis='已知目录用途'):
        rules[path.casefold()] = (owner, basis, action, reason)

    windows = relative_to_drive(root, os.environ.get('SystemRoot', '')) or 'Windows'
    data = relative_to_drive(root, os.environ.get('ProgramData', '')) or 'ProgramData'
    for path, owner, reason in (
        (windows, 'Microsoft Windows', '系统、驱动和维护文件。'),
        (windows + r'\Installer', 'Windows Installer', '供应用修复、更新和卸载使用。'),
        (windows + r'\WinSxS', 'Windows 组件库', 'Windows 维护使用，部分文件与其他系统目录共享硬链接。'),
        (windows + r'\System32\DriverStore', 'Windows 驱动仓库', '供设备驱动安装与维护使用。'),
        ('Recovery', 'Windows 恢复环境', '用于恢复或修复 Windows。'),
        ('$WinREAgent', 'Windows 恢复环境更新', '供 Windows 恢复环境更新与回滚使用。'),
        ('$SysReset', 'Windows 重置', '包括系统重置日志和恢复工作文件。'),
        ('System Volume Information', 'Windows 卷保护', '可存放还原点和其他卷维护数据。'),
        ('Config.Msi', 'Windows Installer', '供安装及回滚使用。'),
        (data + r'\Package Cache', 'Windows 安装维护', '供已安装软件维修或卸载使用。'),
        (data + r'\Microsoft', 'Microsoft 软件和 Windows', '多套组件的共享数据。'),
        (data + r'\Microsoft\Windows Defender', 'Microsoft Defender', 'Windows 防病毒服务的文件。'),
        ('inetpub', 'Windows / IIS', 'Windows 或 IIS 服务可能使用此目录。'),
        ('PerfLogs', 'Windows 性能日志', 'Windows 性能监控目录。'),
    ):
        add(path, owner, KEEP, reason)
    for path, owner, label in (
        (windows + r'\Temp', 'Windows 临时文件', '临时文件'),
        (windows + r'\SoftwareDistribution\Download', 'Windows 更新暂存', 'Windows 更新清理'),
        (windows + r'\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache',
         'Windows 传递优化', '传递优化文件'),
    ):
        add(path, owner, SYSTEM, f'等更新任务完成后，在设置 → 系统 → 存储 → 临时文件核对「{label}」。')
    add('$Recycle.Bin', 'Windows 回收站', RECYCLE, '从回收站核对对应盘的项目，确认无需恢复后处理。')
    for store in sorted(stores):
        add(store, 'Microsoft Store 应用', KEEP, '受保护的应用安装目录。逐个应用从系统设置管理。')
    for path in ('Program Files', 'Program Files (x86)'):
        add(path + r'\Common Files', '已安装软件共享组件', KEEP, '多套应用共用的程序组件。')
    containers = ('users', 'programdata', 'program files', 'program files (x86)')
    profile = relative_to_drive(root, os.environ.get('USERPROFILE', '')).casefold()
    for path, owner in programs.items():
        # Registry entries that point at Windows or a shared system directory do not change its handling.
        if path not in rules and path not in (*containers, profile) and not path.startswith(windows.casefold() + '\\'):
            add(path, owner, APP, '卸载登记指向此路径。确认不用后从应用卸载入口处理。', '本机应用安装登记')
    for path, owner in packages.items():
        add(path, owner, APP, '商店应用由 Windows 管理，核对已安装的应用是否提供卸载。', '本机商店应用登记')
    return rules


# These suffixes are relative to a Windows user profile, never tied to an account name.
PROFILE_RULES = {
    '.codex': ('Codex', KEEP, '可包含会话、活动运行数据和偏好配置。'),
    '.vscode': ('Visual Studio Code', APP, '编辑器扩展。通过扩展管理处理单个闲置扩展。'),
    '.continue': ('Continue', ARCHIVE, '可包含设置和生成的索引。逐项核对后归档。'),
    r'.continue\index': ('Continue', CLEAN, '生成的代码索引。停用扩展并退出编辑器后处理。'),
    '.gradle': ('Gradle', ARCHIVE, '依赖缓存、发行包和用户设置。核对离线构建和配置。'),
    r'.gradle\caches': ('Gradle', CLEAN, '可重建的 Gradle 缓存。退出构建任务后核对。'),
    '.m2': ('Maven', ARCHIVE, '本地仓库和配置，可能包含只存在于本机的构建产物。'),
    '.jdks': ('Java / IDE SDK', ARCHIVE, '需要核对开发工具和项目的 SDK 引用。'),
    'xwechat_files': ('微信', APP, '聊天记录和附件。使用微信存储管理选择需要处理的数据。'),
    r'Documents\Tencent Files': ('QQ', APP, '聊天记录和资料。使用 QQ 的文件和存储管理。'),
    r'Documents\WeChat Files': ('旧版微信', ARCHIVE, '核对历史聊天文件和附件是否还需保留。'),
    r'AppData\Roaming\DBeaverData': ('DBeaver', ARCHIVE, '可能包含数据库连接、驱动和 SQL 脚本。'),
    r'AppData\Roaming\Code': ('Visual Studio Code', KEEP, '设置、工作区数据和缓存混合。逐个子目录核对。'),
    r'AppData\Roaming\Code\CachedExtensionVSIXs': ('Visual Studio Code', CLEAN, '扩展安装包缓存。退出编辑器并确认没有更新后再处理。'),
    r'AppData\Local\Microsoft\Edge': ('Microsoft Edge', KEEP, '浏览器资料和缓存。使用浏览器设置管理。'),
    r'AppData\Local\Microsoft\Edge SxS': ('Microsoft Edge Canary', ARCHIVE, 'Canary 浏览器资料。核对使用情况以及历史和书签后归档。'),
    r'AppData\Local\Google\Chrome': ('Google Chrome', KEEP, '浏览器资料和缓存。使用浏览器设置管理。'),
    r'AppData\Roaming\Mozilla\Firefox': ('Firefox', KEEP, '浏览器资料与设置。使用浏览器的资料管理入口。'),
    r'AppData\Roaming\LarkShell': ('飞书', APP, '客户端资料与缓存。可从飞书设置清理本地缓存。'),
    r'AppData\Roaming\Kingsoft': ('金山软件 / WPS', APP, '应用插件、缓存、设置与文档备份。用 WPS 内置入口核对。'),
    r'AppData\Roaming\Tencent\QQ': ('QQ', APP, '客户端资料和缓存。使用 QQ 设置核对。'),
    r'AppData\Roaming\Tencent\WeChat': ('旧版微信', APP, '旧客户端资料。确认聊天记录和附件后处理。'),
    r'AppData\Roaming\Tencent\xwechat': ('微信', APP, '客户端设置和组件。通过微信设置管理。'),
    r'AppData\Roaming\Tencent\WXWork': ('企业微信', APP, '企业微信资料和组件。用应用存储管理核对。'),
    r'AppData\Local\calibre-cache\ev2\t': ('Calibre', CLEAN, '电子书查看器的临时转换文件。退出查看器之后处理。'),
    r'AppData\Local\Temp': ('Windows 用户临时文件', SYSTEM, '可能有安装程序正在使用。通过 Windows 的临时文件清理入口处理。'),
    r'AppData\Local\Package Cache': ('应用安装维护', KEEP, '可能供已安装应用维修和卸载使用。'),
    r'AppData\Local\Programs': ('当前用户安装的软件', APP, '逐个核对应用，使用应用的卸载入口。'),
}
PROFILE_RULES = {key.casefold(): value for key, value in PROFILE_RULES.items()}
WEB_CACHES = {'cache', 'code cache', 'gpucache', 'grshadercache', 'dawnwebgpucache', 'dawngraphitecache'}
WEB_APPS = {'Microsoft Edge', 'Microsoft Edge Canary', 'Google Chrome', 'Visual Studio Code'}
PERSONAL = {'desktop', 'documents', 'downloads', 'pictures', 'music', 'videos', 'onedrive', 'saved games'}


def classify(row, parent, rules, current_profile):
    relative = row[0]
    path = relative.casefold()
    exact = rules.get(path)
    bits = relative.split('\\')
    if row[2] == '链接或挂载点':
        return (exact[0] if exact else '目录链接', '重解析点', UNREAD, '目标未展开。核对链接指向的位置和软件用途。')
    if row[2].startswith('无法完整读取'):
        owner = exact[0] if exact else parent[0]
        return (owner, '读取有缺项', UNREAD, '权限或扫描期间的变化限制了读取。')
    if exact:
        return exact

    leaf = bits[-1].casefold()
    if len(bits) == 1:
        if path in ('users', 'programdata', 'program files', 'program files (x86)'):
            return (bits[0], 'Windows 目录结构', KEEP, '此目录汇集多个账户或应用。请逐个查看子目录。')
        return (bits[0], '仅目录名线索', CHECK, '根据目录名识别到此标签。用途需进一步确认。')

    profile_depth = 0
    if bits[0].casefold() == 'users':
        profile_depth = 2
    if current_profile and (path == current_profile or path.startswith(current_profile + '\\')):
        profile_depth = len(current_profile.split('\\'))
    if profile_depth:
        suffix_bits = bits[profile_depth:]
        suffix = '\\'.join(suffix_bits).casefold()
        depth = len(suffix_bits)
        if suffix in PROFILE_RULES:
            owner, decision, reason = PROFILE_RULES[suffix]
            return (owner, '已知目录用途', decision, reason)
        if depth == 0 or (depth in (1, 2) and suffix_bits[0].casefold() == 'appdata'):
            return ('Windows 用户资料', 'Windows 目录结构', KEEP, '目录中含多个应用或多类数据，应逐项核对。')
        if depth == 3 and suffix.startswith(('appdata\\local\\', 'appdata\\locallow\\', 'appdata\\roaming\\')):
            return (bits[-1], '仅目录名线索', CHECK, '名称提示软件或厂商，目录可能同时含设置、缓存和个人资料。')
        if depth == 1 and leaf in PERSONAL:
            return ('个人文件', 'Windows 用户目录', ARCHIVE, '核对内容与备份后选择具体个人文件。')
        if depth == 1:
            return (bits[-1], '仅目录名线索', CHECK, '可能是用户数据、应用目录或项目。请先识别用途。')
        if leaf in WEB_CACHES and parent[0] in WEB_APPS:
            return (parent[0], '已知网页缓存目录', CLEAN, '缓存通常可以重建。退出应用后处理，浏览器也可使用内置清理。')
    if len(bits) == 2 and bits[0].casefold() in ('program files', 'program files (x86)', 'programdata'):
        return (bits[1], '仅目录名线索', CHECK, '确认软件归属和使用情况后再选用卸载或应用清理入口。')
    return parent
