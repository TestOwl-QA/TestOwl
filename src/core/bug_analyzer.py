"""
报错分析增强模块 - 提供结构化的错误分析和建议
"""
import re
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ErrorPattern:
    """错误模式定义"""
    pattern: str
    name: str
    severity: str  # critical, high, medium, low
    description: str
    common_causes: List[str]
    suggested_fixes: List[str]


class BugAnalyzer:
    """报错分析器"""
    
    # 内置错误模式库
    ERROR_PATTERNS = [
        # Java 异常
        ErrorPattern(
            pattern=r'NullPointerException',
            name='空指针异常',
            severity='critical',
            description='尝试访问空对象的成员变量或方法',
            common_causes=[
                '对象未初始化就被使用',
                '方法返回null但调用方未检查',
                '异步回调中对象已被销毁',
                '多线程环境下对象状态不一致'
            ],
            suggested_fixes=[
                '添加null检查：if (obj != null)',
                '使用Optional包装可能为null的返回值',
                '在对象销毁时清理回调引用',
                '添加同步机制或volatile关键字'
            ]
        ),
        ErrorPattern(
            pattern=r'IndexOutOfBoundsException|ArrayIndexOutOfBoundsException',
            name='数组越界',
            severity='critical',
            description='访问数组或列表时索引超出有效范围',
            common_causes=[
                '循环条件错误（i <= length 应该是 i < length）',
                '并发修改导致size变化',
                '空列表未检查直接访问元素',
                '计算索引时整数溢出'
            ],
            suggested_fixes=[
                '检查边界：if (index >= 0 && index < list.size())',
                '使用增强for循环替代索引遍历',
                '并发环境使用CopyOnWriteArrayList',
                '添加空列表检查：if (list != null && !list.isEmpty())'
            ]
        ),
        ErrorPattern(
            pattern=r'ClassNotFoundException|NoClassDefFoundError',
            name='类未找到',
            severity='high',
            description='JVM无法加载指定的类',
            common_causes=[
                '缺少依赖jar包',
                '类路径配置错误',
                'ProGuard/R8混淆导致类名改变',
                '动态加载类时拼写错误'
            ],
            suggested_fixes=[
                '检查build.gradle依赖配置',
                '确认混淆规则保留了相关类',
                '清理并重新构建项目',
                '检查类名拼写和包名'
            ]
        ),
        ErrorPattern(
            pattern=r'OutOfMemoryError',
            name='内存溢出',
            severity='critical',
            description='JVM堆内存不足',
            common_causes=[
                '内存泄漏（未释放的引用）',
                '加载过大的资源文件',
                '缓存无限制增长',
                '递归调用过深'
            ],
            suggested_fixes=[
                '使用内存分析工具查找泄漏点',
                '大文件使用流式读取',
                '为缓存设置LRU策略和大小限制',
                '优化递归为迭代实现'
            ]
        ),
        ErrorPattern(
            pattern=r'StackOverflowError',
            name='栈溢出',
            severity='critical',
            description='调用栈深度超过限制',
            common_causes=[
                '无限递归',
                '循环依赖调用',
                '回调链过长'
            ],
            suggested_fixes=[
                '检查递归终止条件',
                '使用循环替代递归',
                '打破循环依赖'
            ]
        ),
        ErrorPattern(
            pattern=r'IllegalArgumentException',
            name='非法参数',
            severity='medium',
            description='方法接收到不合法的参数',
            common_causes=[
                '未验证用户输入直接传递',
                '空字符串或空白字符',
                '数值超出有效范围'
            ],
            suggested_fixes=[
                '在方法入口添加参数校验',
                '使用断言或预条件检查',
                '提供有意义的错误信息'
            ]
        ),
        ErrorPattern(
            pattern=r'IllegalStateException',
            name='非法状态',
            severity='medium',
            description='对象状态不允许执行该操作',
            common_causes=[
                '对象未初始化完成就被使用',
                '资源已关闭仍尝试访问',
                '多线程状态竞争'
            ],
            suggested_fixes=[
                '添加状态检查逻辑',
                '使用状态机管理生命周期',
                '同步状态变更操作'
            ]
        ),
        ErrorPattern(
            pattern=r'ConcurrentModificationException',
            name='并发修改',
            severity='high',
            description='集合在遍历时被修改',
            common_causes=[
                '遍历时删除元素',
                '多线程同时读写',
                '回调中修改集合'
            ],
            suggested_fixes=[
                '使用Iterator.remove()',
                '使用CopyOnWriteArrayList/ConcurrentHashMap',
                '遍历时先复制集合',
                '添加同步机制'
            ]
        ),
        ErrorPattern(
            pattern=r'NumberFormatException',
            name='数字格式错误',
            severity='medium',
            description='字符串无法解析为数字',
            common_causes=[
                '空字符串或null',
                '包含非数字字符',
                '数值超出类型范围'
            ],
            suggested_fixes=[
                '解析前使用正则验证',
                '使用try-catch包装',
                '提供默认值'
            ]
        ),
        ErrorPattern(
            pattern=r'ParseException|JSONException|JsonSyntaxException',
            name='解析异常',
            severity='medium',
            description='数据格式解析失败',
            common_causes=[
                'JSON格式不合法',
                '缺少必要字段',
                '字段类型不匹配',
                '编码问题'
            ],
            suggested_fixes=[
                '使用JSON Schema验证',
                '添加字段缺失检查',
                '统一使用UTF-8编码',
                '记录原始数据便于排查'
            ]
        ),
        # Android 特定
        ErrorPattern(
            pattern=r'ANR|Application Not Responding',
            name='应用无响应',
            severity='critical',
            description='主线程阻塞超过5秒',
            common_causes=[
                '主线程执行耗时操作',
                '死锁',
                '大量UI更新',
                'BroadcastReceiver执行超时'
            ],
            suggested_fixes=[
                '耗时操作移到后台线程',
                '使用AsyncTask/HandlerThread',
                '优化UI层级减少绘制',
                '使用JobScheduler处理后台任务'
            ]
        ),
        ErrorPattern(
            pattern=r'Resources\$NotFoundException',
            name='资源未找到',
            severity='high',
            description='引用的资源不存在',
            common_causes=[
                '资源ID错误',
                '资源被删除或重命名',
                '多语言资源缺失',
                '动态加载资源名错误'
            ],
            suggested_fixes=[
                '检查R文件引用',
                '确认资源存在于所有密度/语言目录',
                '使用try-catch包装动态加载',
                '清理项目重新构建'
            ]
        ),
        ErrorPattern(
            pattern=r'NetworkOnMainThreadException',
            name='主线程网络请求',
            severity='high',
            description='Android 4.0+ 禁止主线程网络操作',
            common_causes=[
                '在主线程直接调用HTTP请求',
                '未使用异步任务',
                'SDK内部网络操作'
            ],
            suggested_fixes=[
                '使用OkHttp+Callback',
                '使用RxJava/协程',
                '使用WorkManager处理网络任务',
                'StrictMode检测违规'
            ]
        ),
        # Unity 特定
        ErrorPattern(
            pattern=r'MissingReferenceException',
            name='Unity引用丢失',
            severity='high',
            description='引用的GameObject或Component已被销毁',
            common_causes=[
                '对象被销毁但引用未清空',
                '场景切换后对象不存在',
                '预制体实例化问题'
            ],
            suggested_fixes=[
                '使用null检查或?.操作符',
                '在OnDestroy中清理引用',
                '使用FindObjectOfType动态查找',
                '使用WeakReference'
            ]
        ),
        ErrorPattern(
            pattern=r'UnassignedReferenceException',
            name='Unity未赋值引用',
            severity='medium',
            description='Inspector中未赋值必需的引用',
            common_causes=[
                '预制体字段未拖拽赋值',
                '代码中[SerializeField]字段为空',
                '动态加载失败'
            ],
            suggested_fixes=[
                '检查Inspector面板所有字段',
                '代码中添加[RequireComponent]',
                '运行时动态获取组件',
                '添加null检查并给出警告'
            ]
        ),
    ]
    
    def __init__(self):
        self.patterns = self.ERROR_PATTERNS.copy()
    
    def analyze(self, error_text: str) -> Dict:
        """
        分析错误日志
        
        Args:
            error_text: 错误日志文本
            
        Returns:
            分析报告
        """
        if not error_text or not error_text.strip():
            return {
                'has_error': False,
                'message': '未检测到错误信息'
            }
        
        # 提取堆栈信息
        stack_info = self._extract_stack_trace(error_text)
        
        # 匹配错误模式
        matched_patterns = []
        for pattern in self.patterns:
            if re.search(pattern.pattern, error_text, re.IGNORECASE):
                matched_patterns.append(pattern)
        
        # 按严重程度排序
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        matched_patterns.sort(key=lambda p: severity_order.get(p.severity, 4))
        
        # 生成报告
        report = {
            'has_error': True,
            'error_count': len(matched_patterns),
            'stack_info': stack_info,
            'matched_patterns': [
                {
                    'name': p.name,
                    'severity': p.severity,
                    'description': p.description,
                    'common_causes': p.common_causes,
                    'suggested_fixes': p.suggested_fixes
                }
                for p in matched_patterns[:3]  # 只返回前3个最匹配的
            ],
            'summary': self._generate_summary(matched_patterns, stack_info)
        }
        
        return report
    
    def _extract_stack_trace(self, text: str) -> Dict:
        """提取堆栈信息"""
        lines = text.split('\n')
        
        # 提取异常类型和消息
        exception_match = re.search(r'(\w+(?:Exception|Error))\s*:\s*(.+)', text)
        exception_type = exception_match.group(1) if exception_match else 'Unknown'
        exception_msg = exception_match.group(2) if exception_match else ''
        
        # 提取堆栈行
        stack_lines = []
        for line in lines:
            # Java堆栈格式: at com.example.Class.method(File.java:123)
            if 'at ' in line and ('(' in line and ')' in line):
                stack_lines.append(line.strip())
        
        # 提取关键位置（第一个应用代码位置）
        key_location = None
        for line in stack_lines:
            # 排除系统类
            if not any(sys in line for sys in ['java.', 'android.', 'sun.', 'dalvik.']):
                match = re.search(r'at ([\w\.]+)\.(\w+)\(([\w\.]+):(\d+)\)', line)
                if match:
                    key_location = {
                        'class': match.group(1),
                        'method': match.group(2),
                        'file': match.group(3),
                        'line': match.group(4)
                    }
                    break
        
        return {
            'exception_type': exception_type,
            'exception_message': exception_msg,
            'stack_depth': len(stack_lines),
            'key_location': key_location,
            'first_party_frames': len([l for l in stack_lines if not any(sys in l for sys in ['java.', 'android.'])])
        }
    
    def _generate_summary(self, patterns: List[ErrorPattern], stack_info: Dict) -> str:
        """生成分析摘要"""
        if not patterns:
            return "未识别到已知错误模式，建议检查日志完整性"
        
        critical_count = sum(1 for p in patterns if p.severity == 'critical')
        high_count = sum(1 for p in patterns if p.severity == 'high')
        
        parts = []
        if critical_count > 0:
            parts.append(f"发现{critical_count}个严重错误")
        if high_count > 0:
            parts.append(f"{high_count}个高危问题")
        
        if stack_info['key_location']:
            loc = stack_info['key_location']
            parts.append(f"问题位置：{loc['file']}:{loc['line']}")
        
        return "；".join(parts) if parts else "发现潜在问题，建议查看详细分析"
    
    def generate_html_report(self, report: Dict) -> str:
        """生成HTML格式的分析报告"""
        if not report.get('has_error'):
            return "<p>未检测到错误信息</p>"
        
        html = ["<h3>🔍 错误分析报告</h3>"]
        
        # 摘要
        html.append(f"<p><strong>{report['summary']}</strong></p>")
        
        # 堆栈信息
        stack = report.get('stack_info', {})
        if stack:
            html.append("<h4>📍 异常位置</h4>")
            html.append(f"<p>类型：<code>{stack.get('exception_type', 'Unknown')}</code></p>")
            if stack.get('key_location'):
                loc = stack['key_location']
                html.append(f"<p>位置：<code>{loc['class']}.{loc['method']}</code><br>")
                html.append(f"文件：{loc['file']}:{loc['line']}</p>")
        
        # 匹配的模式
        patterns = report.get('matched_patterns', [])
        if patterns:
            html.append("<h4>🎯 问题诊断</h4>")
            for i, p in enumerate(patterns, 1):
                severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(p['severity'], '⚪')
                html.append(f"<div style='margin:10px 0;padding:10px;background:#f5f5f5;border-radius:5px;'>")
                html.append(f"<p>{severity_emoji} <strong>{p['name']}</strong> ({p['severity']})</p>")
                html.append(f"<p>{p['description']}</p>")
                
                html.append("<p><strong>常见原因：</strong></p><ul>")
                for cause in p['common_causes'][:3]:  # 只显示前3个
                    html.append(f"<li>{cause}</li>")
                html.append("</ul>")
                
                html.append("<p><strong>建议修复：</strong></p><ul>")
                for fix in p['suggested_fixes'][:3]:
                    html.append(f"<li>{fix}</li>")
                html.append("</ul></div>")
        
        return "\n".join(html)


# 便捷函数
def analyze_bug(error_text: str) -> Dict:
    """快速分析错误"""
    analyzer = BugAnalyzer()
    return analyzer.analyze(error_text)


def analyze_bug_html(error_text: str) -> str:
    """快速分析并返回HTML报告"""
    analyzer = BugAnalyzer()
    report = analyzer.analyze(error_text)
    return analyzer.generate_html_report(report)
