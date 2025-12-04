import customtkinter as ctk
import threading
import requests
import json
import os
import urllib3
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    'pickup': os.path.join(BASE_DIR, "pickup_data.json"),
    'users': os.path.join(BASE_DIR, "users.json"),
    'questname': os.path.join(BASE_DIR, "questname.json"),
    'collectible': os.path.join(BASE_DIR, "claimquest.json"),
    'targets': os.path.join(BASE_DIR, "targets.json"),
    'config': os.path.join(BASE_DIR, "config.json")
}

DEFAULT_USER_AGENT = 'Sky-Live-com.tgc.sky.win/0.28.1.310103 (To Be Filled By O.E.M.; win 10.0.22621; en)'
BASE_URL = 'https://live.radiance.thatgamecompany.com'

class ConfigManager:
    @staticmethod
    def load_config() -> Dict:
        default = {
            'user_agent': DEFAULT_USER_AGENT,
            'max_workers': 10,
            'request_timeout': 10,
            'max_retries': 3
        }
        if not os.path.exists(FILES['config']):
            ConfigManager.save_config(default)
            return default
        try:
            with open(FILES['config'], 'r', encoding='utf-8') as f:
                return {**default, **json.load(f)}
        except:
            return default
    
    @staticmethod
    def save_config(config: Dict) -> bool:
        try:
            with open(FILES['config'], 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            return True
        except:
            return False

class SkyAPIClient:
    def __init__(self, session_id: str, user_id: str, config: Dict):
        self.session_id = session_id
        self.user_id = user_id
        self.config = config
        self.session = requests.Session()
        self.session.verify = False
        
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Host': 'live.radiance.thatgamecompany.com',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'session': self.session_id,
            'user': self.user_id,
            'User-Agent': self.config['user_agent'],
            'user-id': self.user_id
        }
    
    def _make_request(self, endpoint: str, data: Dict, req_type: str, name: str) -> Tuple[str, Optional[str]]:
        url = f"{BASE_URL}{endpoint}"
        for attempt in range(1, self.config['max_retries'] + 1):
            try:
                resp = self.session.post(url, headers=self._get_headers(), json=data, timeout=self.config['request_timeout'])
                if resp.status_code == 200:
                    return "success", resp.json().get("result", "Success")
                elif resp.status_code == 401:
                    return "fail", "Unauthorized"
                elif attempt == self.config['max_retries']:
                    return "fail", f"HTTP {resp.status_code}"
            except requests.exceptions.Timeout:
                logging.warning(f"Timeout {req_type} {name} attempt {attempt}")
            except Exception as e:
                logging.error(f"Error {req_type} {name}: {e}")
            if attempt < self.config['max_retries']:
                time.sleep(2 ** attempt)
        return "fail", "Max retries"
    
    def collect_pickup_batch(self, level_id: str, pickup_ids: List):
        data = {"emitters": [], "global_pickup_ids": [], "level_id": level_id, "pickup_ids": pickup_ids,
                "session": self.session_id, "user": self.user_id, "user_id": self.user_id}
        return self._make_request("/account/collect_pickup_batch", data, "Level", level_id)
    
    def get_account_world_quests(self):
        data = {"session": self.session_id, "user": self.user_id, "user_id": self.user_id}
        return self._make_request("/account/get_account_world_quests", data, "Pre", "Pre")
    
    def claim_quest_reward(self, name: str):
        data = {"bonus_percent": 0, "name": name, "session": self.session_id, "user": self.user_id, "user_id": self.user_id}
        return self._make_request("/account/claim_quest_reward", data, "Quest", name)
    
    def collect_collectible(self, name: str):
        data = {"carrying": False, "name": name, "session": self.session_id, "user": self.user_id, "user_id": self.user_id}
        return self._make_request("/account/collect_collectible", data, "Collectible", name)
    
    def send_light(self, target_id: str, target_name: str):
        data = {"gift_type": "gift_heart_wax", "session": self.session_id, "target": target_id,
                "user": self.user_id, "user_id": self.user_id}
        return self._make_request("/service/relationship/api/v1/free_gifts/send", data, "Light", target_name)
    
    def send_heart(self, target_id: str, target_name: str):
        data = {"gift_type": "gift", "session": self.session_id, "target": target_id,
                "user": self.user_id, "user_id": self.user_id}
        return self._make_request("/account/send_message", data, "Heart", target_name)
    
    def close(self):
        self.session.close()

class FileManager:
    @staticmethod
    def load_json(path: str, default=None):
        if default is None:
            default = []
        if not os.path.exists(path):
            return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    
    @staticmethod
    def save_json(path: str, data):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except:
            return False

class SettingsWindow:
    def __init__(self, parent, config: Dict, callback):
        self.config = config.copy()
        self.callback = callback
        
        self.win = ctk.CTkToplevel(parent)
        self.win.title("Settings")
        self.win.geometry("550x450")
        self.win.transient(parent)
        self.win.grab_set()
        
        ctk.CTkLabel(self.win, text="⚙️ Application Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # User Agent
        ua_frame = ctk.CTkFrame(self.win)
        ua_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(ua_frame, text="User Agent:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,5))
        self.ua_entry = ctk.CTkTextbox(ua_frame, height=80)
        self.ua_entry.pack(padx=10, pady=(0,10), fill="x")
        self.ua_entry.insert("1.0", config['user_agent'])
        
        # Advanced
        adv_frame = ctk.CTkFrame(self.win)
        adv_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(adv_frame, text="Advanced Settings:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,5))
        
        # Workers
        w_frame = ctk.CTkFrame(adv_frame)
        w_frame.pack(padx=10, pady=5, fill="x")
        ctk.CTkLabel(w_frame, text="Max Workers:").pack(side="left", padx=5)
        self.workers = ctk.CTkEntry(w_frame, width=80)
        self.workers.pack(side="left", padx=5)
        self.workers.insert(0, str(config['max_workers']))
        ctk.CTkLabel(w_frame, text="(1-20)", text_color="gray").pack(side="left")
        
        # Timeout
        t_frame = ctk.CTkFrame(adv_frame)
        t_frame.pack(padx=10, pady=5, fill="x")
        ctk.CTkLabel(t_frame, text="Request Timeout:").pack(side="left", padx=5)
        self.timeout = ctk.CTkEntry(t_frame, width=80)
        self.timeout.pack(side="left", padx=5)
        self.timeout.insert(0, str(config['request_timeout']))
        ctk.CTkLabel(t_frame, text="(seconds)", text_color="gray").pack(side="left")
        
        # Retries
        r_frame = ctk.CTkFrame(adv_frame)
        r_frame.pack(padx=10, pady=(5,10), fill="x")
        ctk.CTkLabel(r_frame, text="Max Retries:").pack(side="left", padx=5)
        self.retries = ctk.CTkEntry(r_frame, width=80)
        self.retries.pack(side="left", padx=5)
        self.retries.insert(0, str(config['max_retries']))
        ctk.CTkLabel(r_frame, text="(1-10)", text_color="gray").pack(side="left")
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.win)
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Reset", command=self._reset, fg_color="gray").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Save", command=self._save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.win.destroy, fg_color="red").pack(side="left", padx=5)
    
    def _reset(self):
        self.ua_entry.delete("1.0", "end")
        self.ua_entry.insert("1.0", DEFAULT_USER_AGENT)
        self.workers.delete(0, "end")
        self.workers.insert(0, "10")
        self.timeout.delete(0, "end")
        self.timeout.insert(0, "10")
        self.retries.delete(0, "end")
        self.retries.insert(0, "3")
    
    def _save(self):
        try:
            ua = self.ua_entry.get("1.0", "end").strip()
            if not ua:
                raise ValueError("User Agent cannot be empty")
            workers = int(self.workers.get())
            if not 1 <= workers <= 20:
                raise ValueError("Max Workers: 1-20")
            timeout = int(self.timeout.get())
            if timeout < 1:
                raise ValueError("Timeout >= 1")
            retries = int(self.retries.get())
            if not 1 <= retries <= 10:
                raise ValueError("Max Retries: 1-10")
            
            self.config.update({'user_agent': ua, 'max_workers': workers, 'request_timeout': timeout, 'max_retries': retries})
            if ConfigManager.save_config(self.config):
                self.callback(self.config)
                self.win.destroy()
        except ValueError as e:
            ctk.CTkLabel(self.win, text=str(e), text_color="red").pack()

class SkyAutomationGUI:
    def __init__(self):
        self.users, self.targets = [], []
        self.selected_user_index = None
        self.target_vars = {}
        self.log_lock = Lock()
        self.config = ConfigManager.load_config()
        self._init_gui()
        self._load_data()
    
    def _init_gui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root = ctk.CTk()
        self.root.title("ALT Auto CR | By ReiN")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Menu
        menu = ctk.CTkFrame(self.root)
        menu.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(menu, text="ALT Auto CR", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=10)
        ctk.CTkButton(menu, text="⚙️ Settings", command=self._open_settings, width=100, fg_color="transparent", border_width=1).pack(side="right", padx=5)
        
        # Users
        self.user_list = ctk.CTkScrollableFrame(self.root, width=300, height=150)
        self.user_list.pack(pady=5)
        
        inp = ctk.CTkFrame(self.root)
        inp.pack(pady=5)
        self.nick = ctk.CTkEntry(inp, placeholder_text="Nickname", width=140)
        self.nick.pack(side="left", padx=5)
        self.uid = ctk.CTkEntry(inp, placeholder_text="User ID", width=140)
        self.uid.pack(side="left", padx=5)
        
        btn = ctk.CTkFrame(self.root)
        btn.pack(pady=5)
        ctk.CTkButton(btn, text="Add User", command=self._add_user).pack(side="left", padx=5)
        ctk.CTkButton(btn, text="Delete User", command=self._delete_user).pack(side="left", padx=5)
        
        self.session = ctk.CTkEntry(self.root, placeholder_text="Session ID (auto-pastes from clipboard)", width=350)
        self.session.pack(pady=5)
        
        # Actions
        act = ctk.CTkFrame(self.root)
        act.pack(pady=5)
        ctk.CTkButton(act, text="Start CR", command=self._start_cr).pack(side="left", padx=5)
        ctk.CTkButton(act, text="Start World Quest", command=self._start_quest).pack(side="left", padx=5)
        ctk.CTkButton(self.root, text="Send Light & Heart", command=self._start_gifts).pack(pady=5)
        
        # Targets
        tgt = ctk.CTkFrame(self.root)
        tgt.pack(pady=5)
        tinp = ctk.CTkFrame(tgt)
        tinp.pack(pady=5)
        self.tname = ctk.CTkEntry(tinp, placeholder_text="Target Name", width=140)
        self.tname.pack(side="left", padx=5)
        self.tid = ctk.CTkEntry(tinp, placeholder_text="Target ID", width=140)
        self.tid.pack(side="left", padx=5)
        
        tbtn = ctk.CTkFrame(tgt)
        tbtn.pack(pady=5)
        ctk.CTkButton(tbtn, text="Add Target", command=self._add_target).pack(side="left", padx=5)
        ctk.CTkButton(tbtn, text="Delete Selected", command=self._delete_targets).pack(side="left", padx=5)
        
        self.tlist = ctk.CTkScrollableFrame(tgt, width=300, height=100)
        self.tlist.pack(pady=5)
        
        # Log
        self.log = ctk.CTkTextbox(self.root, width=400, height=150)
        self.log.pack(pady=5)
        ctk.CTkButton(self.root, text="Clear Log", command=lambda: self.log.delete("1.0", "end")).pack(pady=5)
        
        # Progress
        self.progress = ctk.CTkProgressBar(self.root, width=400)
        self.progress.pack(pady=5)
        self.progress.set(0)
        self.prog_count = self.prog_total = 0
        
        # Status
        self.status = ctk.CTkLabel(self.root, text=f"UA: {self.config['user_agent'][:40]}...", text_color="gray", font=ctk.CTkFont(size=9))
        self.status.pack(pady=(0,5))
    
    def _open_settings(self):
        SettingsWindow(self.root, self.config, self._on_config_saved)
    
    def _on_config_saved(self, cfg):
        self.config = cfg
        self._log("Settings saved", "success")
        self.status.configure(text=f"UA: {cfg['user_agent'][:40]}...")
    
    def _log(self, msg: str, lvl="info"):
        with self.log_lock:
            colors = {"error": "red", "success": "yellow", "info": "white", "warning": "orange"}
            prefixes = {"error": "[ERROR]", "success": "[✓]", "info": "[i]", "warning": "[!]"}
            text = f"{prefixes.get(lvl, '[i]')} {msg}\n"
            self.root.after(0, lambda: (self.log.insert("end", text), self.log.tag_config(lvl, foreground=colors.get(lvl, "white")), self.log.see("end")))
    
    def _update_progress(self, inc=True):
        if inc and self.prog_total > 0:
            self.prog_count += 1
            self.root.after(0, lambda: self.progress.set(self.prog_count / self.prog_total))
        else:
            self.root.after(0, lambda: self.progress.set(0))
    
    def _load_data(self):
        self.users = FileManager.load_json(FILES['users'], [])
        self.targets = FileManager.load_json(FILES['targets'], [])
        self._display_users()
        self._display_targets()
    
    def _validate(self):
        try:
            clip = self.root.clipboard_get()
            if clip:
                self.session.delete(0, "end")
                self.session.insert(0, clip.strip())
        except:
            pass
        
        sid = self.session.get().strip()
        if not sid:
            self._log("Session ID required", "error")
            return None, None
        if self.selected_user_index is None or self.selected_user_index >= len(self.users):
            self._log("Select a user", "error")
            return None, None
        return sid, self.users[self.selected_user_index]
    
    def _add_user(self):
        nick = self.nick.get().strip()
        uid = self.uid.get().strip()
        if not nick or not uid:
            self._log("Nickname and User ID required", "error")
            return
        self.users.append({"nickname": nick, "user_id": uid})
        if FileManager.save_json(FILES['users'], self.users):
            self._log(f"User '{nick}' added", "success")
            self._display_users()
            self.nick.delete(0, "end")
            self.uid.delete(0, "end")
    
    def _delete_user(self):
        if self.selected_user_index is None:
            self._log("No user selected", "error")
            return
        user = self.users.pop(self.selected_user_index)
        if FileManager.save_json(FILES['users'], self.users):
            self._log(f"User '{user['nickname']}' deleted", "success")
            self.selected_user_index = None
            self._display_users()
    
    def _display_users(self):
        for w in self.user_list.winfo_children():
            w.destroy()
        for idx, u in enumerate(self.users):
            if not isinstance(u, dict) or 'nickname' not in u:
                continue
            def cb(i=idx, user=u):
                return lambda: (setattr(self, 'selected_user_index', i), self._log(f"Selected: {user['nickname']}", "info"))
            ctk.CTkButton(self.user_list, text=f"{u['nickname']} | ...{u['user_id'][-4:]}", command=cb()).pack(fill="x", pady=2)
    
    def _add_target(self):
        name = self.tname.get().strip()
        tid = self.tid.get().strip()
        if not name or not tid:
            self._log("Target name and ID required", "error")
            return
        self.targets.append({"name": name, "user_id": tid})
        if FileManager.save_json(FILES['targets'], self.targets):
            self._log(f"Target '{name}' added", "success")
            self._display_targets()
            self.tname.delete(0, "end")
            self.tid.delete(0, "end")
    
    def _delete_targets(self):
        sel = [t for t in self.targets if self.target_vars.get(t['user_id'], ctk.BooleanVar()).get()]
        if not sel:
            self._log("No targets selected", "error")
            return
        for t in sel:
            self.targets.remove(t)
        if FileManager.save_json(FILES['targets'], self.targets):
            self._log(f"Deleted {len(sel)} target(s)", "success")
            self._display_targets()
    
    def _display_targets(self):
        for w in self.tlist.winfo_children():
            w.destroy()
        self.target_vars.clear()
        for t in self.targets:
            var = ctk.BooleanVar(value=False)
            self.target_vars[t['user_id']] = var
            ctk.CTkCheckBox(self.tlist, text=f"{t['name']} | ...{t['user_id'][-4:]}", variable=var).pack(fill="x", pady=2)
    
    def _start_cr(self):
        sid, user = self._validate()
        if not sid or not user:
            return
        threading.Thread(target=self._process_cr, args=(sid, user['user_id']), daemon=True).start()
    
    def _process_cr(self, sid, uid):
        self.log.delete("1.0", "end")
        self._log("Starting CR...", "info")
        if not os.path.exists(FILES['pickup']):
            self._log("pickup_data.json not found", "error")
            return
        
        client = SkyAPIClient(sid, uid, self.config)
        try:
            with open(FILES['pickup'], 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip()]
            self.prog_count = 0
            self.prog_total = len(lines)
            self._update_progress(inc=False)
            
            def proc(line):
                try:
                    data = json.loads(line)
                    lid = data.get("level_id")
                    pids = data.get("pickup_ids")
                    if lid and pids:
                        st, res = client.collect_pickup_batch(lid, pids)
                        self._log(f"Level {lid}: {res}", "success" if st == "success" else "error")
                        self._update_progress()
                except Exception as e:
                    self._log(f"Error: {e}", "error")
            
            with ThreadPoolExecutor(max_workers=self.config['max_workers']) as ex:
                list(ex.map(proc, lines))
            self._log("CR complete", "success")
        except Exception as e:
            self._log(f"CR error: {e}", "error")
        finally:
            client.close()
    
    def _start_quest(self):
        sid, user = self._validate()
        if not sid or not user:
            return
        threading.Thread(target=self._process_quest, args=(sid, user['user_id']), daemon=True).start()
    
    def _process_quest(self, sid, uid):
        self.log.delete("1.0", "end")
        self._log("Starting quests...", "info")
        quests = FileManager.load_json(FILES['questname'], [])
        collectibles = FileManager.load_json(FILES['collectible'], [])
        if not quests and not collectibles:
            self._log("No quests/collectibles", "error")
            return
        
        client = SkyAPIClient(sid, uid, self.config)
        try:
            st, res = client.get_account_world_quests()
            if st != "success":
                self._log("Pre-process failed", "error")
                return
            self._log("Pre-process OK", "success")
            
            for q in quests:
                st, res = client.claim_quest_reward(q)
                self._log(f"Quest '{q}': {res}", "success" if st == "success" else "error")
            
            for c in collectibles:
                st, res = client.collect_collectible(c)
                self._log(f"Collectible '{c}': {res}", "success" if st == "success" else "error")
            
            self._log("Quest/collectible complete", "success")
        except Exception as e:
            self._log(f"Quest error: {e}", "error")
        finally:
            client.close()
    
    def _start_gifts(self):
        sid, user = self._validate()
        if not sid or not user:
            return
        sel = [t for t in self.targets if self.target_vars.get(t['user_id'], ctk.BooleanVar()).get()]
        if not sel:
            self._log("No targets selected", "error")
            return
        threading.Thread(target=self._process_gifts, args=(sid, user['user_id'], sel), daemon=True).start()
    
    def _process_gifts(self, sid, uid, targets):
        self.log.delete("1.0", "end")
        self._log("Sending gifts...", "info")
        client = SkyAPIClient(sid, uid, self.config)
        try:
            for t in targets:
                st, res = client.send_light(t['user_id'], t['name'])
                self._log(f"Light to {t['name']}: {res}", "success" if st == "success" else "error")
                st, res = client.send_heart(t['user_id'], t['name'])
                self._log(f"Heart to {t['name']}: {res}", "success" if st == "success" else "error")
            self._log("Gifts sent", "success")
        except Exception as e:
            self._log(f"Gift error: {e}", "error")
        finally:
            client.close()
    
    def _on_closing(self):
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    SkyAutomationGUI().run()