"""
OpenName Search for Android
KivyMD + Material You Design
Themes: Pixel Blue, Mint Green, Sunset Rose
"""

import asyncio
import random
import string
import itertools
import time
from typing import List, Tuple

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.core.window import Window
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineListItem
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.icondefinitions import md_icons
import aiohttp

# ============================================================================
#                           ЛОГИКА БОТА
# ============================================================================

LATIN_LOWER = string.ascii_lowercase
DIGITS = string.digits
ALL_ALPHANUMERIC = LATIN_LOWER + DIGITS
VALID_TG_CHARS = ALL_ALPHANUMERIC + "_"
VOWELS = "aeiouy"
CONSONANTS = "bcdfghjklmnpqrstvwxz"
PREMIUM_PREFIXES = ["x", "z", "q", "v", "j", "k", "y", "w", "ex", "re", "un"]

REQUEST_TIMEOUT = 3.0
BATCH_SIZE = 8
CONCURRENT_CONNECTIONS = 12
DELAY_BETWEEN_REQUESTS = 0.12

class UsernameValidator:
    @staticmethod
    def is_valid(username: str) -> bool:
        if not username:
            return False
        username = username.lower()
        length = len(username)
        if length < 5 or length > 32:
            return False
        if username[0] not in LATIN_LOWER:
            return False
        if username[-1] == "_":
            return False
        if "__" in username:
            return False
        for char in username:
            if char not in VALID_TG_CHARS:
                return False
        return True

class NickGenerator:
    @staticmethod
    def generate_pure_random(length: int, allow_digits: bool = False) -> str:
        first_char = random.choice(LATIN_LOWER)
        pool = ALL_ALPHANUMERIC if allow_digits else LATIN_LOWER
        body = "".join(random.choice(pool) for _ in range(length - 1))
        return first_char + body

    @staticmethod
    def generate_pretty_pronounceable(length: int, allow_digits: bool = False) -> str:
        start_with_vowel = random.choice([True, False])
        res = []
        for i in range(length):
            if allow_digits and i == length - 1 and random.random() < 0.25:
                res.append(random.choice(DIGITS))
                continue
            if (i % 2 == 0) == start_with_vowel:
                res.append(random.choice(VOWELS))
            else:
                res.append(random.choice(CONSONANTS))
        nick = "".join(res[:length])
        if nick[0] not in LATIN_LOWER:
            nick = random.choice(LATIN_LOWER) + nick[1:]
        return nick

    @staticmethod
    def generate_batch(length: int, style: str, size: int = 8) -> List[str]:
        batch = set()
        while len(batch) < size:
            if style == "pretty":
                nick = NickGenerator.generate_pretty_pronounceable(length, allow_digits=False)
            elif style == "pretty_digits":
                nick = NickGenerator.generate_pretty_pronounceable(length, allow_digits=True)
            elif style == "random_digits":
                nick = NickGenerator.generate_pure_random(length, allow_digits=True)
            else:
                nick = NickGenerator.generate_pure_random(length, allow_digits=False)
            if UsernameValidator.is_valid(nick):
                batch.add(nick)
        return list(batch)

    @staticmethod
    def build_mask_combinations(mask: str, limit: int = 1500) -> List[str]:
        mask = mask.lower().strip()
        pools = []
        for idx, char in enumerate(mask):
            if idx == 0:
                if char in ["?", "@"]:
                    pools.append(LATIN_LOWER)
                elif char in LATIN_LOWER:
                    pools.append([char])
                else:
                    return []
            else:
                if char == "?":
                    pools.append(ALL_ALPHANUMERIC)
                elif char == "@":
                    pools.append(LATIN_LOWER)
                elif char == "#":
                    pools.append(DIGITS)
                elif char in VALID_TG_CHARS:
                    pools.append([char])
                else:
                    return []
        combos = []
        for item in itertools.product(*pools):
            cand = "".join(item)
            if UsernameValidator.is_valid(cand):
                combos.append(cand)
                if len(combos) >= limit:
                    break
        random.shuffle(combos)
        return combos

class LiquidityEngine:
    @classmethod
    def evaluate(cls, nick: str) -> Tuple[int, str, List[str]]:
        nick = nick.lower()
        score = 4
        tags = []
        length = len(nick)
        if length == 5:
            score += 3
            tags.append("5-значный")
        elif length == 6:
            score += 1
            tags.append("6-значный")
        vowels_count = sum(1 for c in nick if c in VOWELS)
        vowel_ratio = vowels_count / length
        if 0.3 <= vowel_ratio <= 0.6:
            score += 2
            tags.append("Читаемый")
        elif vowels_count == 0:
            score -= 2
            tags.append("Без гласных")
        digits_count = sum(1 for c in nick if c.isdigit())
        if digits_count == 0:
            score += 2
            tags.append("Чистый текст")
        elif digits_count == 1 and nick[-1].isdigit():
            score += 1
            tags.append("Цифра в конце")
        if any(nick.startswith(pref) for pref in PREMIUM_PREFIXES):
            score += 1
            tags.append("Редкий префикс")
        score = max(1, min(score, 10))
        if score >= 9:
            grade = "LEGENDARY"
        elif score >= 7:
            grade = "EPIC"
        elif score >= 5:
            grade = "RARE"
        else:
            grade = "COMMON"
        return score, grade, tags

class NetworkScanner:
    @classmethod
    async def verify_username(cls, session: aiohttp.ClientSession, nick: str) -> bool:
        if not UsernameValidator.is_valid(nick):
            return False
        frag_url = f"https://fragment.com/username/{nick}"
        tg_url = f"https://t.me/{nick}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            async with session.get(tg_url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as tg_resp:
                if tg_resp.status == 200:
                    tg_html = await tg_resp.text()
                    if '<div class="tgme_page_title"' in tg_html and '<span dir="auto">' in tg_html:
                        return False
                    if "tgme_page_photo_image" in tg_html:
                        return False
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
            async with session.get(frag_url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as frag_resp:
                if frag_resp.status == 200:
                    frag_html = await frag_resp.text()
                    if "tm-status-taken" in frag_html:
                        return False
                    if "Minimum bid" in frag_html or "Winning bid" in frag_html:
                        return False
                    return True
            return False
        except Exception:
            return False

# ============================================================================
#                           KV LAYOUT
# ============================================================================

KV = '''
<ThemeCard@MDCard>:
    radius: 16
    size_hint_y: None
    height: 60
    md_bg_color: app.theme_cls.primary_light

MDScreen:
    md_bg_color: app.theme_cls.bg_dark
    
    MDTopAppBar:
        id: toolbar
        title: "OpenName Search"
        elevation: 0
        pos_hint: {"top": 1}
        md_bg_color: app.theme_cls.primary_dark
        
        right_action_items:
            [["cog", lambda x: app.open_theme_menu()]]
    
    MDBottomNavigation:
        id: nav
        panel_color: app.theme_cls.primary_dark
        selected_color_background: app.theme_cls.primary_light
        text_color_active: app.theme_cls.primary_light
        text_color_inactive: app.theme_cls.text_secondary
        
        MDBottomNavigationItem:
            name: "search"
            text: "Поиск"
            icon: "magnify"
            
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(16)
                spacing: dp(12)
                
                MDCard:
                    orientation: "vertical"
                    size_hint_y: None
                    height: dp(220)
                    radius: 20
                    elevation: 2
                    md_bg_color: app.theme_cls.card_dark
                    padding: dp(16)
                    spacing: dp(12)
                    
                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        spacing: dp(12)
                        
                        MDLabel:
                            text: "Длина"
                            size_hint_x: 0.3
                            
                        MDSegmentedControl:
                            id: length_seg
                            size_hint_x: 0.7
                            pos_hint: {"center_y": 0.5}
                            segments:
                                [{"text": "5"}, {"text": "6"}, {"text": "7"}, {"text": "8"}]
                            callback: app.on_length_change
                    
                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(50)
                        spacing: dp(12)
                        
                        MDLabel:
                            text: "Режим"
                            size_hint_x: 0.3
                            
                        MDSegmentedControl:
                            id: style_seg
                            size_hint_x: 0.7
                            pos_hint: {"center_y": 0.5}
                            segments:
                                [{"text": "Слоги"}, {"text": "Буквы"}, {"text": "Цифры"}]
                            callback: app.on_style_change
                    
                    MDRaisedButton:
                        id: search_btn
                        text: "НАЧАТЬ ПОИСК"
                        md_bg_color: app.theme_cls.primary_light
                        font_size: dp(16)
                        size_hint_y: None
                        height: dp(50)
                        on_release: app.start_search()
                
                MDCard:
                    size_hint_y: None
                    height: dp(80)
                    radius: 20
                    elevation: 1
                    md_bg_color: app.theme_cls.card_dark
                    padding: dp(16)
                    
                    MDBoxLayout:
                        spacing: dp(12)
                        
                        MDIcon:
                            icon: "progress-clock"
                            size_hint_x: 0.1
                            
                        MDLabel:
                            id: status_label
                            text: "Готов к поиску"
                            font_size: dp(14)
                            theme_text_color: "Secondary"
        
        MDBottomNavigationItem:
            name: "mask"
            text: "Маска"
            icon: "asterisk"
            
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(16)
                spacing: dp(12)
                
                MDCard:
                    orientation: "vertical"
                    size_hint_y: None
                    height: dp(300)
                    radius: 20
                    elevation: 2
                    md_bg_color: app.theme_cls.card_dark
                    padding: dp(16)
                    spacing: dp(12)
                    
                    MDLabel:
                        text: "Синтаксис маски:"
                        font_size: dp(14)
                        theme_text_color: "Secondary"
                    
                    MDLabel:
                        text: "• @ — буква (a-z)\\n• # — цифра (0-9)\\n• ? — любой символ"
                        font_size: dp(13)
                        theme_text_color: "Secondary"
                    
                    MDTextField:
                        id: mask_input
                        hint_text: "Пример: ro??x"
                        mode: "rectangle"
                        size_hint_y: None
                        height: dp(50)
                    
                    MDRaisedButton:
                        id: mask_btn
                        text: "ИСКАТЬ ПО МАСКЕ"
                        md_bg_color: app.theme_cls.primary_light
                        font_size: dp(16)
                        size_hint_y: None
                        height: dp(50)
                        on_release: app.start_mask_search()
                
                MDCard:
                    size_hint_y: None
                    height: dp(60)
                    radius: 20
                    elevation: 1
                    md_bg_color: app.theme_cls.card_dark
                    padding: dp(16)
                    
                    MDLabel:
                        id: mask_status
                        text: "Введите маску"
                        font_size: dp(14)
                        theme_text_color: "Secondary"
        
        MDBottomNavigationItem:
            name: "history"
            text: "История"
            icon: "history"
            
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(16)
                spacing: dp(12)
                
                MDCard:
                    orientation: "vertical"
                    radius: 20
                    elevation: 2
                    md_bg_color: app.theme_cls.card_dark
                    padding: dp(8)
                    
                    MDScrollView:
                        MDList:
                            id: history_list
                            spacing: dp(4)
                
                MDBoxLayout:
                    size_hint_y: None
                    height: dp(50)
                    spacing: dp(12)
                    
                    MDRaisedButton:
                        text: "ОЧИСТИТЬ"
                        md_bg_color: app.theme_cls.error_light
                        size_hint_x: 0.5
                        on_release: app.clear_history()
                    
                    MDRaisedButton:
                        text: "ЭКСПОРТ"
                        md_bg_color: app.theme_cls.primary_light
                        size_hint_x: 0.5
                        on_release: app.export_history()
    
    MDBoxLayout:
        size_hint_y: None
        height: dp(30)
        md_bg_color: app.theme_cls.bg_dark
        padding: dp(8)
        
        MDLabel:
            text: "made by @CLL_studio"
            theme_text_color: "Custom"
            text_color: [0.3, 0.3, 0.4, 1]
            font_size: dp(11)
            halign: "center"
'''

class OpenNameSearchApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.themes = {
            "Pixel Blue": {
                "primary": "#1A73E8",
                "primary_light": "#4A8CFF",
                "primary_dark": "#0D47A1",
                "bg_dark": "#0F0F1A",
                "card_dark": "#1A1A2E",
                "text_secondary": "#888899"
            },
            "Mint Green": {
                "primary": "#00C853",
                "primary_light": "#4ADE80",
                "primary_dark": "#007A2E",
                "bg_dark": "#0D1A0F",
                "card_dark": "#1A2E1A",
                "text_secondary": "#889988"
            },
            "Sunset Rose": {
                "primary": "#FF4081",
                "primary_light": "#FF6BA6",
                "primary_dark": "#B71C4C",
                "bg_dark": "#1A0D14",
                "card_dark": "#2E1A24",
                "text_secondary": "#998899"
            }
        }
        self.current_theme = "Pixel Blue"
        self.history = []
        self.is_searching = False
        self.search_task = None
        self.checked = 0
        self.length = 5
        self.style = "pretty"
        self.menu = None
        self.load_history()
        self.selected_color = self.themes[self.current_theme]["primary"]
        self.theme_cls.primary_palette = "Blue"

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.apply_theme(self.current_theme)
        return Builder.load_string(KV)

    def apply_theme(self, theme_name):
        t = self.themes[theme_name]
        self.theme_cls.primary_light = t["primary_light"]
        self.theme_cls.primary_dark = t["primary_dark"]
        self.theme_cls.primary = t["primary"]
        self.theme_cls.bg_dark = t["bg_dark"]
        self.theme_cls.card_dark = t["card_dark"]
        self.theme_cls.text_secondary = t["text_secondary"]
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Blue"
        self.current_theme = theme_name

    def open_theme_menu(self):
        menu_items = [
            {"text": "Pixel Blue", "viewclass": "OneLineListItem", "on_release": lambda x="Pixel Blue": self.change_theme(x)},
            {"text": "Mint Green", "viewclass": "OneLineListItem", "on_release": lambda x="Mint Green": self.change_theme(x)},
            {"text": "Sunset Rose", "viewclass": "OneLineListItem", "on_release": lambda x="Sunset Rose": self.change_theme(x)}
        ]
        self.menu = MDDropdownMenu(
            items=menu_items,
            width_mult=4,
            max_height=200,
            bg_color=self.theme_cls.card_dark,
            text_color="white"
        )
        self.menu.open()

    def change_theme(self, theme_name):
        self.apply_theme(theme_name)
        if self.menu:
            self.menu.dismiss()
        Snackbar(text=f"Тема: {theme_name}", duration=1.5).open()

    def on_length_change(self, segment):
        self.length = int(segment.text)

    def on_style_change(self, segment):
        style_map = {"Слоги": "pretty", "Буквы": "random", "Цифры": "random_digits"}
        self.style = style_map.get(segment.text, "pretty")

    def start_search(self):
        if self.is_searching:
            self.stop_search()
            return
        
        self.is_searching = True
        self.checked = 0
        btn = self.root.ids.search_btn
        btn.text = "ОСТАНОВИТЬ"
        btn.md_bg_color = self.theme_cls.error_light
        self.root.ids.status_label.text = "Поиск..."
        self.search_task = self.start_async_search()

    def start_mask_search(self):
        if self.is_searching:
            return
        mask = self.root.ids.mask_input.text.strip()
        if not mask or len(mask) < 5:
            Snackbar(text="Минимум 5 символов!").open()
            return
        self.is_searching = True
        self.checked = 0
        btn = self.root.ids.mask_btn
        btn.text = "ОСТАНОВИТЬ"
        btn.md_bg_color = self.theme_cls.error_light
        self.root.ids.mask_status.text = "Поиск..."
        self.search_task = self.start_async_mask_search(mask)

    def start_async_search(self):
        async def search():
            connector = aiohttp.TCPConnector(limit=CONCURRENT_CONNECTIONS)
            async with aiohttp.ClientSession(connector=connector) as session:
                while self.is_searching:
                    batch = NickGenerator.generate_batch(self.length, self.style, size=BATCH_SIZE)
                    tasks = [NetworkScanner.verify_username(session, nick) for nick in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for nick, is_free in zip(batch, results):
                        if not self.is_searching:
                            break
                        self.checked += 1
                        Clock.schedule_once(lambda x, c=self.checked: self.update_status(c), 0)
                        if is_free is True:
                            Clock.schedule_once(lambda x, n=nick: self.on_found(n), 0)
                            return
                    await asyncio.sleep(0.001)
            Clock.schedule_once(lambda x: self.on_search_end(), 0)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.create_task(search())

    def start_async_mask_search(self, mask):
        async def search():
            combos = NickGenerator.build_mask_combinations(mask, limit=1500)
            total = len(combos)
            if total == 0:
                Clock.schedule_once(lambda x: Snackbar(text="Некорректная маска").open(), 0)
                Clock.schedule_once(lambda x: self.on_search_end(), 0)
                return
            connector = aiohttp.TCPConnector(limit=CONCURRENT_CONNECTIONS)
            async with aiohttp.ClientSession(connector=connector) as session:
                for i in range(0, total, BATCH_SIZE):
                    if not self.is_searching:
                        break
                    batch = combos[i:i+BATCH_SIZE]
                    tasks = [NetworkScanner.verify_username(session, nick) for nick in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for nick, is_free in zip(batch, results):
                        if not self.is_searching:
                            break
                        self.checked += 1
                        Clock.schedule_once(lambda x, c=self.checked: self.update_mask_status(c), 0)
                        if is_free is True:
                            Clock.schedule_once(lambda x, n=nick: self.on_found(n), 0)
                            return
                    await asyncio.sleep(0.001)
            Clock.schedule_once(lambda x: self.on_search_end(), 0)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.create_task(search())

    def update_status(self, checked):
        self.root.ids.status_label.text = f"Проверено: {checked}"

    def update_mask_status(self, checked):
        self.root.ids.mask_status.text = f"Проверено: {checked}"

    def on_found(self, nick):
        self.is_searching = False
        score, grade, tags = LiquidityEngine.evaluate(nick)
        self.history.append(nick)
        self.save_history()
        self.add_to_history(nick, score, grade, tags)
        self.root.ids.status_label.text = f"✅ @{nick} ({score}/10)"
        self.root.ids.mask_status.text = f"✅ @{nick} ({score}/10)"
        Snackbar(text=f"@{nick} найден! Скопирован", duration=3).open()

    def add_to_history(self, nick, score, grade, tags):
        list_item = OneLineListItem(
            text=f"@{nick}  •  {score}/10  •  {grade}",
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_light
        )
        list_item.bind(on_release=lambda x, n=nick: self.copy_nick(n))
        self.root.ids.history_list.add_widget(list_item)

    def copy_nick(self, nick):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(nick)
        Snackbar(text=f"@{nick} скопирован", duration=1.5).open()

    def on_search_end(self):
        self.is_searching = False
        if hasattr(self, 'search_task') and self.search_task:
            try:
                self.search_task.cancel()
            except:
                pass
        btn = self.root.ids.search_btn
        btn.text = "НАЧАТЬ ПОИСК"
        btn.md_bg_color = self.theme_cls.primary_light
        mask_btn = self.root.ids.mask_btn
        mask_btn.text = "ИСКАТЬ ПО МАСКЕ"
        mask_btn.md_bg_color = self.theme_cls.primary_light
        if self.checked > 0 and not self.root.ids.status_label.text.startswith("✅"):
            self.root.ids.status_label.text = f"❌ Ников не найдено ({self.checked} проверено)"
            self.root.ids.mask_status.text = f"❌ Ников не найдено ({self.checked} проверено)"

    def stop_search(self):
        self.is_searching = False
        if hasattr(self, 'search_task') and self.search_task:
            try:
                self.search_task.cancel()
            except:
                pass
        self.on_search_end()

    def clear_history(self):
        self.history.clear()
        self.root.ids.history_list.clear_widgets()
        self.save_history()
        Snackbar(text="История очищена", duration=1.5).open()

    def export_history(self):
        if not self.history:
            Snackbar(text="История пуста", duration=1.5).open()
            return
        from kivy.storage.jsonstore import JsonStore
        store = JsonStore("exported_history.json")
        store.put("history", items=self.history)
        Snackbar(text=f"Экспортировано {len(self.history)} ников", duration=2).open()

    def load_history(self):
        try:
            from kivy.storage.jsonstore import JsonStore
            store = JsonStore("history.json")
            self.history = store.get("history")["items"]
        except:
            self.history = []
        for nick in self.history:
            score, grade, tags = LiquidityEngine.evaluate(nick)
            self.add_to_history(nick, score, grade, tags)

    def save_history(self):
        try:
            from kivy.storage.jsonstore import JsonStore
            store = JsonStore("history.json")
            store.put("history", items=self.history)
        except:
            pass

if __name__ == "__main__":
    OpenNameSearchApp().run()