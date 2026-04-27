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
        # 系统/网络错误
        ErrorPattern(
            pattern=r'Errno 98.*address already in use|Address already in use',
            name='端口被占用',
            severity='high',
            description='服务启动时端口已被其他进程占用',
            common_causes=[
                '上次服务未完全关闭，进程仍在后台运行',
                '其他程序占用了该端口',
                '服务异常退出导致端口未释放',
                '快速重启服务，端口还在TIME_WAIT状态'
            ],
            suggested_fixes=[
                '查找并结束占用端口的进程：lsof -ti:8081 | xargs kill -9',
                '等待几秒让系统释放端口后重试',
                '更换服务端口：--port 8082',
                '使用pkill强制结束：pkill -9 -f "uvicorn"'
            ]
        ),
        ErrorPattern(
            pattern=r'Connection refused|ConnectionRefusedError',
            name='连接被拒绝',
            severity='high',
            description='无法连接到目标服务',
            common_causes=[
                '目标服务未启动',
                '防火墙阻止了连接',
                '连接地址或端口错误',
                '网络不通'
            ],
            suggested_fixes=[
                '检查目标服务是否已启动',
                '检查防火墙规则',
                '验证连接地址和端口是否正确',
                '使用ping/telnet测试网络连通性'
            ]
        ),
        ErrorPattern(
            pattern=r'Timeout|timed out|Read timed out',
            name='连接超时',
            severity='medium',
            description='连接或请求超时',
            common_causes=[
                '网络延迟高',
                '目标服务响应慢',
                '请求处理时间过长',
                '连接池耗尽'
            ],
            suggested_fixes=[
                '增加超时时间设置',
                '检查目标服务负载',
                '优化请求处理逻辑',
                '使用连接池管理'
            ]
        ),
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
        """生成HTML格式的分析报告（可折叠章节样式）"""
        if not report.get('has_error'):
            return "<p>未检测到错误信息</p>"
        
        html = []
        
        # 问题概述（始终展开）
        html.append("<div style='margin-bottom:16px;'>")
        html.append(f"<p style='font-weight:bold;margin-bottom:8px;'>我看到问题了！{report['summary']}</p>")
        html.append("</div>")
        
        # 异常位置（可折叠）
        stack = report.get('stack_info', {})
        if stack and stack.get('exception_type') != 'Unknown':
            html.append("<details style='margin:8px 0;border:1px solid #e0e0e0;border-radius:4px;'>")
            html.append("<summary style='padding:8px 12px;background:#f5f5f5;cursor:pointer;font-weight:bold;'>异常位置</summary>")
            html.append("<div style='padding:12px;'>")
            html.append(f"<p>异常类型：<code>{stack.get('exception_type', 'Unknown')}</code></p>
            if stack.get('key_location'):
                loc = stack['key_location']
                html.append(f"<p>定位：<code>{loc['class']}.{loc['method']}</code></p>")
                html.append(f"<p>文件：{loc['file']}:{loc['line']}</p>")
            html.append("</div>")
            html.append("</details>")
        
        # 问题诊断（可折叠）
        patterns = report.get('matched_patterns', [])
        if patterns:
            for i, p in enumerate(patterns, 1):
                severity_class = {'critical': 'color:#d32f2f;', 'high': 'color:#f57c00;', 'medium': 'color:#f9a825;', 'low': 'color:#388e3c;'}.get(p['severity'], '')
                
                html.append(f"<details style='margin:8px 0;border:1px solid #e0e0e0;border-radius:4px;'>")
                html.append(f"<summary style='padding:8px 12px;background:#f5f5f5;cursor:pointer;font-weight:bold;{severity_class}'>{p['name']}</summary>")
                html.append("<div style='padding:12px;'>")
                html.append(f"<p style='color:#666;margin-bottom:12px;'>{p['description']}</p>")
                
                # 常见原因
                html.append("<p style='font-weight:bold;margin:8px 0 4px;'>可能原因：</p>")
                html.append("<ol style='margin:0;padding-left:20px;'>")
                for cause in p['common_causes']:
                    html.append(f"<li style='margin:4px 0;'>{cause}</li>")
                html.append("</ol>")
                
                # 修复建议
                html.append("<p style='font-weight:bold;margin:12px 0 4px;'>建议修复：</p>")
                html.append("<ol style='margin:0;padding-left:20px;'>")
                for fix in p['suggested_fixes']:
                    html.append(f"<li style='margin:4px 0;'>{fix}</li>")
                html.append("</ol>")
                
                html.append("</div>")
                html.append("</details>")
        
        # 如果没有匹配到模式
        if not patterns:
            html.append("<details style='margin:8px 0;border:1px solid #e0e0e0;border-radius:4px;' open>")
            html.append("<summary style='padding:8px 12px;background:#f5f5f5;cursor:pointer;font-weight:bold;'>问题分析</summary>")
            html.append("<div style='padding:12px;'>")
            html.append("<p>未能识别到已知的错误模式。可能原因：</p>")
            html.append("<ol style='margin:0;padding-left:20px;'>")
            html.append("<li>错误信息不完整，缺少堆栈信息</li>")
            html.append("<li>这是自定义异常，不在常见错误库中</li>")
            html.append("<li>错误日志被截断或格式异常</li>")
            html.append("</ol>")
            html.append("<p style='margin-top:12px;'>建议：提供完整的错误日志，包括异常类型和堆栈信息。</p>")
            html.append("</div>")
            html.append("</details>")
        
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
