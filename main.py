import threading
import sys
import os
import importlib.util
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.clock import Clock

# 重定向标准输出到 UI 文本框
class StreamToLogger(object):
    def __init__(self, app, original_stream):
        self.app = app
        self.original_stream = original_stream
        self.buffer = ''

    def write(self, buf):
        self.original_stream.write(buf)
        self.buffer += buf
        if '\n' in self.buffer:
            Clock.schedule_once(self.flush)

    def flush(self, dt=None):
        if self.buffer:
            if self.app and hasattr(self.app, 'log_output'):
                self.app.log_output.text += self.buffer
            self.buffer = ''
            
    def flush_immediate(self):
        pass

class GongChengApp(App):
    def build(self):
        self.title = "GongCheng Auto (Remote OCR)"
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header
        header = Label(text="GongCheng Automation", size_hint=(1, 0.05), font_size='20sp')
        layout.add_widget(header)
        
        # Configuration Settings
        config_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.1), spacing=5)
        
        config_layout.add_widget(Label(text="OCR Server URL:", size_hint=(0.3, 1)))
        self.server_input = TextInput(text="http://192.168.1.100:5000/ocr", size_hint=(0.7, 1), multiline=False)
        config_layout.add_widget(self.server_input)
        layout.add_widget(config_layout)

        device_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.1), spacing=5)
        device_layout.add_widget(Label(text="Airtest Device:", size_hint=(0.3, 1)))
        # 默认使用无线调试端口或 Android 插件
        self.device_input = TextInput(text="android://127.0.0.1:5555/", size_hint=(0.7, 1), multiline=False)
        device_layout.add_widget(self.device_input)
        layout.add_widget(device_layout)
        
        # Log Output
        self.log_output = TextInput(readonly=True, size_hint=(1, 0.55), multiline=True, font_size='12sp')
        layout.add_widget(self.log_output)
        
        # Controls
        btn_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.2), spacing=10)
        
        self.start_btn = Button(text="Start Script", background_color=(0, 1, 0, 1))
        self.start_btn.bind(on_press=self.start_script)
        btn_layout.add_widget(self.start_btn)
        
        self.stop_btn = Button(text="Stop (Exit App)", background_color=(1, 0, 0, 1))
        self.stop_btn.bind(on_press=self.stop_script)
        btn_layout.add_widget(self.stop_btn)
        
        layout.add_widget(btn_layout)
        
        # Setup logging
        sys.stdout = StreamToLogger(self, sys.__stdout__)
        sys.stderr = StreamToLogger(self, sys.__stderr__)
        
        return layout

    def start_script(self, instance):
        self.start_btn.disabled = True
        
        server_url = self.server_input.text.strip()
        device_uri = self.device_input.text.strip()
        
        # 设置环境变量供 ocr_manager.py 和 gongcheng.py 读取
        os.environ["OCR_SERVER_URL"] = server_url
        os.environ["AIRTEST_DEVICE_URI"] = device_uri
        
        self.log_output.text += f"Using OCR Server: {server_url}\n"
        self.log_output.text += f"Using Device: {device_uri}\n"
        self.log_output.text += "Initializing script in background thread...\n"
        
        # Run in thread
        threading.Thread(target=self.run_gc_logic, daemon=True).start()

    def stop_script(self, instance):
        sys.exit(0)

    def run_gc_logic(self):
        try:
            # 修改 Airtest 设备连接，使用界面上输入的 URI
            from airtest.core.api import auto_setup
            device_uri = os.environ.get("AIRTEST_DEVICE_URI", "android:///")
            auto_setup(__file__, logdir=False, devices=[device_uri])

            # 加载 gongcheng.py
            script_path = os.path.join(os.path.dirname(__file__), "gongcheng.py")
            if not os.path.exists(script_path):
                 print(f"Error: {script_path} not found!")
                 return

            spec = importlib.util.spec_from_file_location("gongcheng_script", script_path)
            gc_module = importlib.util.module_from_spec(spec)
            sys.modules["gongcheng_script"] = gc_module
            spec.loader.exec_module(gc_module)
            
            print("Script loaded. Starting main loop...")
            if hasattr(gc_module, 'main'):
                gc_module.main()
            elif hasattr(gc_module, 'attack_loop'):
                # 兼容旧代码直接调用
                gc_module.attack_loop(gc_module.MY_KINGDOM)
            else:
                print("Warning: No main() or attack_loop() found in gongcheng.py.")
                
        except Exception as e:
            print(f"Script crashed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.start_btn.disabled = False
            print("Script execution ended.")

if __name__ == '__main__':
    GongChengApp().run()
