# game/debug_tool.rpy
init python:
    import json, os, time, re, hashlib, urllib.parse, requests
    import threading, socketserver, http.server
    import traceback, marshal
    from datetime import datetime

    # === Cấu hình ===
    # Google Translate miễn phí — không cần API key
    TARGET_LANG = "vi"          # "vi"=Tiếng Việt | "zh"=Trung | "ja"=Nhật | "ko"=Hàn
    # Dùng đường dẫn tuyệt đối từ gamedir — tránh lạc file trên Android
    _GAMEDIR    = renpy.config.gamedir
    CACHE_FILE  = os.path.join(_GAMEDIR, "translation_cache.json")
    SCRIPTS_DIR = os.path.join(_GAMEDIR, "scripts")
    DUMP_DIR    = os.path.join(_GAMEDIR, "dumps")
    try:
        os.makedirs(SCRIPTS_DIR)
    except OSError:
        pass
    try:
        os.makedirs(DUMP_DIR)
    except OSError:
        pass

    _cache = {}           # {md5: translated}
    _cache_raw = {}       # {md5: original}  — để lưu text gốc vào JSON
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    v = item.get(TARGET_LANG, item.get('zh', ''))
                    if v:  # bỏ qua entry rỗng để dịch lại
                        _cache[item['id']]     = v
                        _cache_raw[item['id']] = item.get('en', '')
        except:
            pass

    def _save_cache():
        data = [
            {"id": k, "en": _cache_raw.get(k, ""), TARGET_LANG: v}
            for k, v in _cache.items()
        ]
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _should_translate(text):
        if not isinstance(text, str):
            return False
        text = text.strip()
        if len(text) < 2:
            return False
        # Bỏ qua nếu toàn ký tự đặc biệt/số
        if not any(c.isalpha() for c in text):
            return False
        # Bỏ qua nếu đã là tiếng Việt (có dấu đặc trưng)
        viet = set('àáâãèéêìíòóôõùúýăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỷỹỵ'
                   'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỶỸỴ')
        if any(c in viet for c in text):
            return False
        # Bỏ qua nếu đã là tiếng Trung/Nhật/Hàn
        if any('\u4e00' <= c <= '\u9fff' for c in text):
            return False
        return True

    def _call_tencent(text):
        # Đã thay bằng Google Translate miễn phí
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl':     'auto',
                'tl':     TARGET_LANG,
                'dt':     't',
                'q':      text
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36'
            }
            r = requests.get(url, params=params, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                translated = ''.join(
                    item[0] for item in data[0] if item and item[0]
                )
                return translated.strip() if translated else None
        except:
            pass
        return None

    def translate_text(text):
        if not isinstance(text, str) or not _should_translate(text):
            return text
        # Chỉ bảo vệ tag Ren'Py [...] và {...}, KHÔNG bảo vệ "..." hay '...'
        parts = re.split(r'(\[[^\]]*\]|\{[^}]*\})', text)
        result = []
        for part in parts:
            if re.match(r'(?:\[.*\]|\{.*\})$', part):
                result.append(part)
            else:
                key = hashlib.md5(part.encode()).hexdigest()
                cached = _cache.get(key, '')
                if cached:  # chỉ dùng cache nếu không rỗng
                    result.append(cached)
                else:
                    trans = _call_tencent(part)
                    if trans:  # bỏ điều kiện trans != part để dịch kể cả khi giống gốc
                        _cache[key]     = trans
                        _cache_raw[key] = part
                        _save_cache()
                        result.append(trans)
                    else:
                        result.append(part)
        final = ''.join(result)
        escaped = ""
        i = 0
        while i < len(final):
            c = final[i]
            in_mark = False
            # Chỉ skip tag [...] và {...}, không skip nháy đơn/đôi
            for s, e in [('[', ']'), ('{', '}')]:
                if c == s:
                    end = final.find(e, i+1)
                    if end != -1:
                        escaped += final[i:end+1]
                        i = end + 1
                        in_mark = True
                        break
            if in_mark:
                continue
            escaped += c * 2 if c in '{}[]%' else c
            i += 1
        return escaped

    def _translate_menu_items(items):
        new_items = []
        for item in items:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                label = item[0]
                rest  = item[1:]
                if isinstance(label, str):
                    label = translate_text(label)
                new_items.append((label,) + tuple(rest))
            else:
                new_items.append(item)
        return new_items

    if not hasattr(renpy, '_original_say'):
        renpy._original_say = renpy.say
        def _hooked_say(who, what, *args, **kwargs):
            if isinstance(what, str):
                what = translate_text(what)
            return renpy._original_say(who, what, *args, **kwargs)
        renpy.say = _hooked_say

    # Hook menu — thử tất cả các cách, luôn set lại mỗi lần init

    # Cách 1: renpy.exports.menu — hoạt động trên JoiPlay
    try:
        import renpy.exports as _rexports
        if not hasattr(_rexports, '_orig_menu'):
            _rexports._orig_menu = _rexports.menu
        def _hooked_exports_menu(items, *args, **kwargs):
            return _rexports._orig_menu(_translate_menu_items(items), *args, **kwargs)
        _rexports.menu = _hooked_exports_menu
    except:
        pass

    # Cách 2: config.menu_text_filter — Ren'Py 8.x
    try:
        renpy.config.menu_text_filter = translate_text
    except:
        pass

    # Cách 3: renpy.display_menu — Ren'Py 7.x fallback
    try:
        if hasattr(renpy, 'display_menu'):
            if not hasattr(renpy, '_original_display_menu') or not callable(renpy._original_display_menu):
                renpy._original_display_menu = renpy.display_menu
            def _hooked_display_menu(items, *args, **kwargs):
                return renpy._original_display_menu(_translate_menu_items(items), *args, **kwargs)
            renpy.display_menu = _hooked_display_menu
    except:
        pass

    # ==================== 脚本执行工具 ====================
    def lochttp(url):
        """从URL加载并执行Python脚本"""
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                code = resp.text
                exec(code, globals())
                return {"status": "success", "message": "Executed script from " + str(url)}
            else:
                return {"status": "error", "message": "HTTP " + str(resp.status_code)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def sdump(output_dir):
        """Dump 所有运行时资源"""
        try:
            full_output = os.path.join(DUMP_DIR, output_dir)
            try:
                os.makedirs(full_output)
            except OSError:
                pass

            all_files = set()
            for fn in renpy.list_files():
                if fn.startswith("cache/") or fn.endswith(".pyc"):
                    continue
                all_files.add(fn)

            dumped_count = 0
            errors = []

            for filepath in sorted(all_files):
                dest_path = os.path.join(full_output, filepath)
                try:
                    os.makedirs(os.path.dirname(dest_path))
                except OSError:
                    pass

                try:
                    if filepath.endswith('.rpy'):
                        try:
                            with open(os.path.join("game", filepath), 'r', encoding='utf-8') as f:
                                content = f.read()
                            with open(dest_path, 'w', encoding='utf-8') as out_f:
                                out_f.write(content)
                            dumped_count += 1
                            continue
                        except:
                            pass

                    if filepath.endswith('.rpyc'):
                        try:
                            data = renpy.file(filepath).read()
                            if data.startswith(b'RPG1'):
                                _, stmts = marshal.loads(data[4:])
                                decompiled = "# Decompiled from .rpyc (approximate)\n# Full recovery not possible.\n"
                                decompiled += "\n".join([str(stmt) for stmt in stmts[:20]])
                                with open(dest_path.replace('.rpyc', '.rpy'), 'w', encoding='utf-8') as out_f:
                                    out_f.write(decompiled)
                                dumped_count += 1
                                continue
                        except Exception as e:
                            errors.append(str(filepath) + ": " + str(e))
                    
                    # 其他文件（图片、音频等）
                    file_data = renpy.file(filepath).read()
                    with open(dest_path, 'wb') as out_f:
                        out_f.write(file_data)
                    dumped_count += 1

                except Exception as e:
                    errors.append(str(filepath) + ": " + str(e))

            if errors:
                with open(os.path.join(full_output, "DUMP_ERRORS.txt"), 'w', encoding='utf-8') as log:
                    log.write("以下文件提取失败:\n")
                    log.write("\n".join(errors))

            return {
                "status": "success",
                "message": "成功提取 " + str(dumped_count) + " 个文件到 " + str(full_output),
                "errors": len(errors)
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    def execute_script_content(code_str, filename="<dynamic>"):
        """安全执行脚本内容"""
        try:
            compiled = compile(code_str, filename, 'exec')
            exec(compiled, globals())
            return {"status": "success", "message": "Script executed successfully."}
        except Exception as e:
            tb = traceback.format_exc()
            return {"status": "error", "message": str(e), "traceback": tb}

    # ==================== 监控器 ====================
    class DebugMonitor:
        def __init__(self):
            self.monitored = {}
            self.selected_vars = []
            self.script_history = []
            self.load()

        def load(self):
            try:
                if os.path.exists("monitor.json"):
                    with open("monitor.json") as f:
                        self.monitored = json.load(f)
            except:
                pass

        def save(self):
            with open("monitor.json", "w") as f:
                json.dump(self.monitored, f)

        def get_all_vars(self):
            import store
            numeric_vars = []
            bool_vars = []
            str_vars = []

            for name in dir(store):
                if name.startswith('_'):
                    continue
                if name.isupper() and len(name) > 4:
                    continue
                if name in ['translator', 'memory_monitor', 'monitor', 'DebugMonitor', 'WEB_PAGE', 'CACHE_FILE', 'SCRIPTS_DIR', 'TARGET_LANG', 'lochttp', 'sdump', 'execute_script_content']:
                    continue

                try:
                    val = getattr(store, name)
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        numeric_vars.append({"name": name, "value": val, "type": "numeric"})
                    elif isinstance(val, bool):
                        bool_vars.append({"name": name, "value": val, "type": "boolean"})
                    elif isinstance(val, str):
                        str_vars.append({"name": name, "value": val, "type": "string"})
                except:
                    pass

            return numeric_vars + bool_vars + str_vars

        def update_variable(self, var_name, new_value):
            import renpy
            old = renpy.store.__dict__.get(var_name, None)
            if isinstance(new_value, str):
                if new_value.lower() in ('true', 'false'):
                    new_val = new_value.lower() == 'true'
                elif new_value.isdigit():
                    new_val = int(new_value)
                elif new_value.replace('.','',1).isdigit():
                    new_val = float(new_value)
                else:
                    new_val = new_value
            else:
                new_val = new_value
            renpy.store.__dict__[var_name] = new_val
            self.monitored[var_name] = new_val
            self.save()
            return {"old": old, "new": new_val}

        def bulk_update_variables(self, updates):
            results = []
            for update in updates:
                var_name = update.get("variable_name")
                new_value = update.get("new_value")
                if var_name and new_value is not None:
                    result = self.update_variable(var_name, new_value)
                    results.append({
                        "name": var_name,
                        "old": result["old"],
                        "new": result["new"],
                        "success": True
                    })
                else:
                    results.append({
                        "name": var_name,
                        "success": False,
                        "error": "参数无效"
                    })
            
            script = "\n".join([str(u.get('variable_name')) + " = " + str(u.get('new_value')) 
                               for u in updates if u.get('variable_name')])
            self.script_history.append({
                "time": time.strftime("%H:%M:%S"),
                "script": script,
                "results": results
            })
            return results

        def list_scripts(self):
            scripts = []
            for file in os.listdir(SCRIPTS_DIR):
                if file.endswith('.py'):
                    scripts.append(file)
            return sorted(scripts)

    monitor = DebugMonitor()

    # ==================== iOS 风格 HTML ====================
    DEBUG_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>面板</title>
    <style>
        :root {
            --bg-color: #000000;
            --bg-gradient: radial-gradient(circle at 50% -20%, #2b3245, #000000 70%);
            --glass-panel: rgba(28, 28, 30, 0.6);
            --glass-border: rgba(255, 255, 255, 0.1);
            --tab-active-bg: rgba(99, 99, 102, 0.6);
            --text-primary: #ffffff;
            --text-secondary: rgba(235, 235, 245, 0.6);
            --success-color: rgba(52, 199, 89, 0.2);
            --warning-color: rgba(255, 204, 0, 0.2);
            --danger-color: rgba(255, 59, 48, 0.2);
            --ease-spring: cubic-bezier(0.25, 0.8, 0.25, 1);
        }

        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
            background: var(--bg-color);
            background-image: var(--bg-gradient);
            min-height: 100vh;
            color: var(--text-primary);
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-top: 20px;
        }

        .ios-badge {
            display: inline-flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(20px);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 16px;
        }

        .system-info {
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 10px;
        }

        .segmented-control {
            position: relative;
            display: flex;
            width: 100%;
            background: rgba(118, 118, 128, 0.24);
            backdrop-filter: blur(20px);
            padding: 2px;
            border-radius: 9px;
            margin-bottom: 30px;
            height: 40px;
        }

        .tab-slider {
            position: absolute;
            top: 2px;
            bottom: 2px;
            left: 2px;
            width: calc(33.333% - 4px);
            background: #636366;
            border-radius: 7px;
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12), 0 3px 1px rgba(0, 0, 0, 0.04);
            transition: transform 0.3s var(--ease-spring);
            z-index: 1;
            border: 0.5px solid rgba(0,0,0,0.04);
        }

        .tab-btn {
            flex: 1;
            position: relative;
            z-index: 2;
            background: none;
            border: none;
            color: var(--text-primary);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            text-align: center;
            line-height: 36px;
            outline: none;
        }

        .content-wrapper {
            background: var(--glass-panel);
            backdrop-filter: blur(40px);
            border-radius: 18px;
            border: 1px solid var(--glass-border);
            padding: 25px;
            margin-bottom: 25px;
        }

        .tab-content {
            display: none;
            animation: fadeIn 0.4s var(--ease-spring);
        }

        .tab-content.active {
            display: block;
        }

        /* 自定义复选框 */
        .custom-checkbox {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 6px;
            position: relative;
            cursor: pointer;
            vertical-align: middle;
            margin-right: 8px;
        }

        .custom-checkbox.checked {
            background: #34c759;
            border-color: #34c759;
        }

        .custom-checkbox.checked::after {
            content: "✓";
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) scale(0.8);
            color: white;
            font-size: 14px;
            font-weight: bold;
        }

        .variables-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 12px;
            margin-top: 20px;
            max-height: 400px;
            overflow-y: auto;
            padding-right: 5px;
        }

        .variable-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 16px;
            transition: all 0.2s ease;
        }

        .variable-card:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: translateY(-2px);
        }

        .variable-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .variable-name {
            font-weight: 600;
            font-size: 14px;
        }

        .variable-value {
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(180deg, #fff 0%, rgba(255,255,255,0.7) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 8px 0;
        }

        .variable-type {
            font-size: 12px;
            color: var(--text-secondary);
            padding: 4px 8px;
            border-radius: 6px;
            background: rgba(255,255,255,0.05);
        }

        .selected-section {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        .selected-list {
            display: grid;
            gap: 10px;
        }

        .selected-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
        }

        .value-edit {
            width: 100px;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            color: var(--text-primary);
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 14px;
        }

        .script-area {
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            font-family: 'SF Mono', monospace;
        }

        .script-textarea {
            width: 100%;
            min-height: 150px;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 14px;
            line-height: 1.5;
            resize: vertical;
            outline: none;
        }

        .script-actions {
            display: flex;
            gap: 12px;
            margin-top: 15px;
        }

        .script-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 10px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .script-btn.generate { background: var(--success-color); color: #34c759; }
        .script-btn.execute { background: var(--warning-color); color: #ffcc00; }
        .script-btn.clear { background: var(--danger-color); color: #ff3b30; }
        .script-btn.dump { background: rgba(0,122,255,0.2); color: #007aff; }

        .history-section, .dump-section {
            margin-top: 30px;
        }

        .history-list, .dump-list {
            max-height: 200px;
            overflow-y: auto;
        }

        .history-item, .dump-item {
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 10px;
            font-size: 13px;
        }

        .history-time {
            color: var(--text-secondary);
            font-size: 12px;
            margin-bottom: 5px;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 3px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="ios-badge">版本V0.2</div>
            <h1 style="margin: 0; font-size: 32px;">面板</h1>
            <p style="color: var(--text-secondary); margin-top: 8px;">BY 我灵机不动</p>
            <div class="system-info" id="systemInfo"></div>
        </div>

        <div class="segmented-control">
            <div class="tab-slider" id="slider"></div>
            <button class="tab-btn active-text" onclick="switchTab(0)">变量提取</button>
            <button class="tab-btn" onclick="switchTab(1)">脚本执行</button>
            <button class="tab-btn" onclick="switchTab(2)">DUMP 工具</button>
        </div>

        <!-- 变量提取 -->
        <div id="tab1-content" class="content-wrapper tab-content active">
            <div class="extract-header">
                <div class="filter-buttons">
                    <button class="filter-btn active" onclick="filterVars('all')">全部</button>
                    <button class="filter-btn" onclick="filterVars('numeric')">数值</button>
                    <button class="filter-btn" onclick="filterVars('boolean')">布尔</button>
                    <button class="filter-btn" onclick="filterVars('string')">字符串</button>
                </div>
                <button class="action-btn" onclick="extractVariables()">立即提取</button>
            </div>
            <div id="variablesList" class="variables-grid"></div>
            <div class="selected-section" id="selectedSection" style="display: none;">
                <div class="selected-header">
                    <h3>已选择 <span id="selectedCount">0</span> 个变量</h3>
                    <div class="script-actions">
                        <button class="script-btn generate" onclick="generateScript()">生成脚本</button>
                        <button class="script-btn clear" onclick="clearSelection()">清空选择</button>
                    </div>
                </div>
                <div id="selectedList" class="selected-list"></div>
            </div>
        </div>

        <!-- 脚本执行 -->
        <div id="tab2-content" class="content-wrapper tab-content">
            <div class="script-area">
                <h3>脚本编辑器</h3>
                <textarea id="scriptOutput" class="script-textarea" placeholder="// 在此编辑脚本...&#10;"></textarea>
                <div class="script-actions">
                    <button class="script-btn execute" onclick="executeScript()">执行脚本</button>
                    <button class="script-btn clear" onclick="clearScript()">清空</button>
                </div>
            </div>
            <div class="dump-section">
                <h3>本地脚本库 (<code>scripts/</code>)</h3>
                <div id="scriptLibrary" class="dump-list"></div>
                <button class="script-btn" onclick="loadScriptLibrary()" style="margin-top:10px;">刷新列表</button>
            </div>
            <div class="history-section">
                <h3>执行历史</h3>
                <div id="historyList" class="history-list"></div>
            </div>
        </div>

        <!-- DUMP 工具 -->
        <div id="tab3-content" class="content-wrapper tab-content">
            <div class="dump-section">
                <h3>DUMP 控制</h3>
                <div class="script-actions" style="margin-top:10px;">
                    <input type="text" id="dumpPath" placeholder="输出目录名 (e.g., my_game_dump)" style="flex:1; background:rgba(0,0,0,0.3); color:white; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.1);">
                    <button class="script-btn dump" onclick="dumpScripts()">执行 DUMP</button>
                </div>
                <div class="script-actions" style="margin-top:10px;">
                    <input type="text" id="httpUrl" placeholder="远程脚本 URL (e.g., https://example.com/script.py)" style="flex:1; background:rgba(0,0,0,0.3); color:white; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.1);">
                    <button class="script-btn execute" onclick="loadRemoteScript()">加载远程脚本</button>
                </div>
            </div>
        </div>

        <div style="text-align: center; margin-top: 30px; color: var(--text-secondary); font-size: 13px;">
            <span id="statusText">就绪</span> • <span id="lastUpdate">-</span>
        </div>
    </div>

    <script>
        let allVariables = [];
        let selectedVars = [];
        let currentFilter = 'all';
        const startTime = Date.now();

        function switchTab(index) {
            const slider = document.getElementById('slider');
            slider.style.transform = `translateX(${index * 100}%)`;
            document.querySelectorAll('.tab-btn').forEach((btn, i) => btn.classList.toggle('active-text', i === index));
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById(`tab${index+1}-content`).classList.add('active');
            if (index === 0 && allVariables.length === 0) extractVariables();
            if (index === 1) { loadHistory(); loadScriptLibrary(); }
            if (index === 2) loadSystemInfo();
        }

        // ========== 工具函数 ==========
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function updateStatus(message, type) {
            const statusEl = document.getElementById('statusText');
            if (!statusEl) return;
            statusEl.textContent = message;
            const colors = { info: 'var(--text-secondary)', success: '#34c759', error: '#ff3b30', warning: '#ffcc00' };
            statusEl.style.color = colors[type] || 'var(--text-primary)';
        }

        function updateLastUpdate() {
            const now = new Date();
            const el = document.getElementById('lastUpdate');
            if (el) el.textContent = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`;
        }

        // ========== 变量提取 ==========
        async function extractVariables() {
            updateStatus('正在提取变量...', 'info');
            try {
                const res = await fetch('/api/variables');
                const data = await res.json();
                if (data.status === 'success') {
                    allVariables = data.variables || [];
                    displayVariables(allVariables);
                    updateStatus(`提取完成，共 ${allVariables.length} 个变量`, 'success');
                    updateLastUpdate();
                } else throw new Error(data.message || '未知错误');
            } catch (e) {
                updateStatus('提取失败: ' + e.message, 'error');
            }
        }

        function displayVariables(vars) {
            const container = document.getElementById('variablesList');
            if (!container) return;
            if (vars.length === 0) {
                container.innerHTML = '<div style="text-align:center; padding:40px; color:var(--text-secondary)">未找到变量</div>';
                return;
            }
            container.innerHTML = vars.map(v => `
                <div class="variable-card">
                    <div class="variable-header">
                        <div class="variable-name">${escapeHtml(v.name)}</div>
                        <div class="variable-type">${v.type}</div>
                    </div>
                    <div class="variable-value">${formatValue(v.value)}</div>
                    <div style="margin-top: 10px;">
                        <span class="custom-checkbox" data-name="${v.name}" data-value="${JSON.stringify(v.value)}" data-type="${v.type}" onclick="toggleVariable(this)"></span>
                        <label style="font-size:13px; color:var(--text-secondary); margin-left: 5px;">选择</label>
                    </div>
                </div>
            `).join('');
            selectedVars.forEach(v => {
                const cb = document.querySelector(`.custom-checkbox[data-name="${v.name}"]`);
                if (cb) cb.classList.add('checked');
            });
        }

        function formatValue(value) {
            if (typeof value === 'boolean') return value ? '✅ true' : '❌ false';
            if (typeof value === 'string') {
                const safe = escapeHtml(value);
                return `"${safe.length > 20 ? safe.substring(0, 20) + '...' : safe}"`;
            }
            return String(value);
        }

        function toggleVariable(el) {
            const name = el.getAttribute('data-name');
            const value = JSON.parse(el.getAttribute('data-value'));
            const type = el.getAttribute('data-type');
            const isChecked = !el.classList.contains('checked');
            el.classList.toggle('checked', isChecked);
            if (isChecked) {
                selectedVars.push({name, value, type});
                document.getElementById('selectedSection').style.display = 'block';
            } else {
                selectedVars = selectedVars.filter(v => v.name !== name);
                if (selectedVars.length === 0) document.getElementById('selectedSection').style.display = 'none';
            }
            updateSelectedDisplay();
        }

        function updateSelectedDisplay() {
            document.getElementById('selectedCount').textContent = selectedVars.length;
            const container = document.getElementById('selectedList');
            if (!container) return;
            container.innerHTML = selectedVars.map((v, i) => `
                <div class="selected-item">
                    <div><strong>${escapeHtml(v.name)}</strong><div style="font-size:12px; color:var(--text-secondary)">${v.type}</div></div>
                    <input type="text" class="value-edit" value="${escapeHtml(String(v.value))}" onchange="updateSelectedValue(${i}, this.value)" placeholder="新值">
                </div>
            `).join('');
        }

        function updateSelectedValue(index, newValue) { selectedVars[index].value = newValue; }

        function filterVars(type) {
            currentFilter = type;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            const filtered = type === 'all' ? allVariables : allVariables.filter(v => v.type === type);
            displayVariables(filtered);
        }

        function clearSelection() {
            selectedVars = [];
            document.querySelectorAll('.custom-checkbox').forEach(cb => cb.classList.remove('checked'));
            document.getElementById('selectedSection').style.display = 'none';
        }

        function generateScript() {
            if (selectedVars.length === 0) { alert('请先选择变量'); return; }
            let script = '';
            selectedVars.forEach(v => {
                if (v.type === 'string') script += `${v.name} = "${v.value}"\n`;
                else script += `${v.name} = ${v.value}\n`;
            });
            document.getElementById('scriptOutput').value = script;
            switchTab(1);
        }

        // ========== 脚本执行 ==========
        async function executeScript() {
            const script = document.getElementById('scriptOutput').value.trim();
            if (!script) { alert('请输入脚本'); return; }
            if (!confirm('确定要执行此脚本吗？')) return;
            updateStatus('正在执行脚本...', 'info');
            try {
                const res = await fetch('/api/execute_raw', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code: script})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    updateStatus('脚本执行成功', 'success');
                    setTimeout(() => extractVariables(), 500);
                    setTimeout(() => loadHistory(), 500);
                } else {
                    updateStatus('执行失败: ' + data.message, 'error');
                }
            } catch (e) {
                updateStatus('网络错误: ' + e.message, 'error');
            }
        }

        function clearScript() {
            if (confirm('确定要清空脚本吗？')) document.getElementById('scriptOutput').value = '';
        }

        async function loadHistory() {
            try {
                const res = await fetch('/api/history');
                const data = await res.json();
                const container = document.getElementById('historyList');
                if (data.status === 'success' && container) {
                    container.innerHTML = (data.history || []).map(h => `
                        <div class="history-item">
                            <div class="history-time">${h.time || '未知时间'}</div>
                            <div style="font-family:monospace; font-size:12px;">${escapeHtml(h.script || '无脚本')}</div>
                        </div>
                    `).join('');
                }
            } catch (e) { console.error(e); }
        }

        // ========== 脚本库 ==========
        async function loadScriptLibrary() {
            try {
                const res = await fetch('/api/scripts');
                const data = await res.json();
                const container = document.getElementById('scriptLibrary');
                if (data.status === 'success' && container) {
                    container.innerHTML = data.scripts.map(f => `
                        <div class="dump-item" onclick="runLocalScript('${f}')">📜 ${escapeHtml(f)}</div>
                    `).join('');
                }
            } catch (e) { console.error(e); }
        }

        async function runLocalScript(filename) {
            if (!confirm(`确定要执行 ${filename} 吗？`)) return;
            updateStatus('正在执行本地脚本...', 'info');
            try {
                const res = await fetch('/api/run_script', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename: filename})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    updateStatus('脚本执行成功', 'success');
                } else {
                    updateStatus('执行失败: ' + data.message, 'error');
                }
            } catch (e) {
                updateStatus('网络错误: ' + e.message, 'error');
            }
        }

        // ========== DUMP & 远程 ==========
        async function dumpScripts() {
            const path = document.getElementById('dumpPath').value.trim();
            if (!path) { alert('请输入目录名'); return; }
            updateStatus('正在执行 DUMP...', 'info');
            try {
                const res = await fetch('/api/dump', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({output_dir: path})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    updateStatus('DUMP 成功: ' + data.message, 'success');
                } else {
                    updateStatus('DUMP 失败: ' + data.message, 'error');
                }
            } catch (e) {
                updateStatus('网络错误: ' + e.message, 'error');
            }
        }

        async function loadRemoteScript() {
            const url = document.getElementById('httpUrl').value.trim();
            if (!url) { alert('请输入 URL'); return; }
            updateStatus('正在加载远程脚本...', 'info');
            try {
                const res = await fetch('/api/lochttp', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    updateStatus('远程脚本执行成功', 'success');
                } else {
                    updateStatus('执行失败: ' + data.message, 'error');
                }
            } catch (e) {
                updateStatus('网络错误: ' + e.message, 'error');
            }
        }

        async function loadSystemInfo() {
            try {
                const res = await fetch('/api/system_info');
                const data = await res.json();
                if (data.status === 'success') {
                    const info = `${data.time} | 运行: ${Math.floor((Date.now() - startTime)/1000)}s | Ren'Py: ${data.renpy_version} | 游戏: ${data.game_version}`;
                    document.getElementById('systemInfo').textContent = info;
                }
            } catch (e) { console.error(e); }
        }

        window.onload = () => {
            switchTab(0);
            setTimeout(() => extractVariables(), 100);
            setInterval(loadSystemInfo, 5000);
        };
    </script>
</body>
</html>
'''

    # ==================== Web 服务处理 ====================
    class DebugHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_html(DEBUG_HTML)
            elif self.path == '/api/variables':
                self.api_variables()
            elif self.path == '/api/history':
                self.api_history()
            elif self.path == '/api/scripts':
                self.api_list_scripts()
            elif self.path == '/api/system_info':
                self.api_system_info()
            else:
                self.send_error(404)

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
            except:
                data = {}

            if self.path == '/api/bulk_update':
                self.api_bulk_update(data)
            elif self.path == '/api/dump':
                self.api_dump(data)
            elif self.path == '/api/lochttp':
                self.api_lochttp(data)
            elif self.path == '/api/run_script':
                self.api_run_script(data)
            elif self.path == '/api/execute_raw':
                self.api_execute_raw(data)
            else:
                self.send_error(404)

        def send_html(self, html):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        def send_json(self, data):
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

        def api_variables(self):
            variables = monitor.get_all_vars()
            self.send_json({"status": "success", "variables": variables, "count": len(variables)})

        def api_bulk_update(self, data):
            updates = data.get("updates", [])
            results = monitor.bulk_update_variables(updates)
            self.send_json({
                "status": "success",
                "updated_count": len([r for r in results if r.get("success")]),
                "results": results
            })

        def api_history(self):
            self.send_json({"status": "success", "history": monitor.script_history[-10:]})

        def api_list_scripts(self):
            scripts = monitor.list_scripts()
            self.send_json({"status": "success", "scripts": scripts})

        def api_system_info(self):
            self.send_json({
                "status": "success",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "renpy_version": renpy.version,
                "game_version": config.version,
            })

        def api_dump(self, data):
            output_dir = data.get("output_dir", "dump")
            result = sdump(output_dir)
            self.send_json(result)

        def api_lochttp(self, data):
            url = data.get("url", "")
            result = lochttp(url)
            self.send_json(result)

        def api_run_script(self, data):
            filename = data.get("filename", "")
            if not filename or not filename.endswith('.py'):
                self.send_json({"status": "error", "message": "仅支持 .py 脚本"})
                return
            script_path = os.path.join(SCRIPTS_DIR, filename)
            if not os.path.exists(script_path):
                self.send_json({"status": "error", "message": "脚本不存在"})
                return
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                result = execute_script_content(code, filename)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)})

        def api_execute_raw(self, data):
            code = data.get("code", "")
            if not code:
                self.send_json({"status": "error", "message": "无脚本内容"})
                return
            result = execute_script_content(code, "<web_editor>")
            self.send_json(result)

        def log_message(self, format, *args):
            pass

    def start_debug_server():
        try:
            server = socketserver.TCPServer(("127.0.0.1", 8889), DebugHandler)
            server.serve_forever()
        except:
            pass

    _t = threading.Thread(target=start_debug_server)
    _t.daemon = True
    _t.start()

screen debug_status():
    zorder 999
    frame:
        xalign 1.0 yalign 0.02
        background "#00000088"
        padding (12, 8)
        vbox:
            text "iOS 调试工具" size 14 color "#FFF"
            textbutton "打开面板" action OpenURL("http://127.0.0.1:8889") text_size 12

label after_load:
    show screen debug_status
    return
