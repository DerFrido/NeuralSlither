from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import SessionNotCreatedException
import gymnasium as gym
import numpy as np
import cv2
import base64
import math
import time
import os
import shutil
import tempfile
import threading
import sys

NICKNAME = "Der_Frido"
MIN_ALIVE_SECONDS = 5.0
RESPAWN_DELAY_SECONDS = 2.5
SPAWN_GRACE_SECONDS = 3.0
MAX_SPAWN_WAIT_STEPS = 350
SPAWN_CONFIRM_RETRIES = 4
SPAWN_CONFIRM_DELAY = 0.4


class SlitherEnv(gym.Env):
    def __init__(self, env_idx=0):
        super().__init__()
        self.env_idx = env_idx

        self.observation_space = gym.spaces.Box(
            low=0, high=255, shape=(160, 160, 1), dtype=np.uint8
        )
        self.action_space = gym.spaces.Discrete(16)

        self.driver = None
        self.profile_dir = os.path.join(
            tempfile.gettempdir(), f"slither_edge_profile_{os.getpid()}_{self.env_idx}"
        )

        self.last_score = 10
        self.peak_score_this_run = 10
        self.steps_this_run = 0
        self.spawn_time = None
        self._spawn_grace_until = 0.0
        self.just_spawned = True

        self._waiting_for_spawn = False
        self._spawn_attempts = 0
        self._last_click_time = 0
        self._spawn_wait_steps = 0
        self._respawn_ready_at = 0.0
        self._initial_spawn_done = False
        self._spawn_triggered_after_delay = False

    # ================================================================
    # BROWSER SETUP
    # ================================================================

    def _start_browser(self):
        os.makedirs(self.profile_dir, exist_ok=True)

        last_error = None
        for attempt in range(3):
            try:
                options = Options()
                options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--window-size=450,450")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-background-timer-throttling")
                options.add_argument("--disable-backgrounding-occluded-windows")
                options.add_argument("--disable-renderer-backgrounding")
                options.add_argument("--disable-gpu")
                options.add_argument("--no-first-run")
                options.add_argument("--no-default-browser-check")
                options.add_argument("--remote-debugging-port=0")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument(f"--user-data-dir={self.profile_dir}")

                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)

                print(f"[Env {self.env_idx}] BROWSER_START attempt {attempt + 1} profile={self.profile_dir}")
                self.driver = webdriver.Edge(options=options)
                self.driver.set_script_timeout(10)
                self.driver.implicitly_wait(5)
                break
            except SessionNotCreatedException as e:
                last_error = e
                print(f"[Env {self.env_idx}] BROWSER_START failed attempt {attempt + 1}: {type(e).__name__}: {e}")
                self.driver = None
                try:
                    shutil.rmtree(self.profile_dir, ignore_errors=True)
                except Exception:
                    pass
                self.profile_dir = os.path.join(
                    tempfile.gettempdir(),
                    f"slither_edge_profile_{os.getpid()}_{self.env_idx}_{time.time_ns()}"
                )
                time.sleep(1.0)
        else:
            raise last_error if last_error else RuntimeError("Edge browser could not be started")

        spalten = 2
        pos_x = (self.env_idx % spalten) * 460
        pos_y = (self.env_idx // spalten) * 460
        self.driver.set_window_position(pos_x, pos_y)

        self._load_page(first_load=True)

    def _load_page(self, first_load=False):
        try:
            if first_load:
                print(f"[Env {self.env_idx}] LOAD_PAGE: fetching slither.io")
                self.driver.get("https://slither.io")
            else:
                print(f"[Env {self.env_idx}] RELOAD_PAGE: page hung, reloading")
                self.driver.get("https://slither.io")

            self._wait_for_dom(timeout=20)
            self._wait_for_canvas(timeout=15)
            time.sleep(1.0)
            print(f"[Env {self.env_idx}] PAGE_READY")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[Env {self.env_idx}] LOAD_ERROR: {type(e).__name__}: {e}")

    def _wait_for_dom(self, timeout=20):
        """Wartet bis DOM-Elemente da sind"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.driver.find_element(By.ID, "nick")
                self.driver.find_element(By.ID, "playh")
                return True
            except:
                time.sleep(0.5)
        print(f"[Env {self.env_idx}] DOM_TIMEOUT after {timeout}s")
        return False

    def _wait_for_canvas(self, timeout=15):
        """Wartet bis Canvas da ist"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                canvas = self.driver.find_element(By.TAG_NAME, "canvas")
                if canvas:
                    return True
            except:
                pass
            time.sleep(0.5)
        print(f"[Env {self.env_idx}] CANVAS_TIMEOUT after {timeout}s")
        return False

    # ================================================================
    # SPIELSTART
    # ================================================================

    def _try_spawn(self):
        t0 = time.time()
        try:
            print(f"[Env {self.env_idx}] SPAWN_ATTEMPT #{self._spawn_attempts+1}")
            
            # Menü-Check
            for attempt in range(10):
                try:
                    rect_w = self.driver.execute_script(
                        "return document.getElementById('nick').getBoundingClientRect().width;"
                    )
                    if rect_w and rect_w > 0:
                        break
                except:
                    pass
                time.sleep(0.1)

            time.sleep(0.2)

            # JS Spawn
            try:
                print(f"[Env {self.env_idx}]   trying JS method")
                self.driver.execute_script(f"""
                    var nick = document.getElementById('nick');
                    if (nick) {{
                        var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                        setter.call(nick, '{NICKNAME}');
                        nick.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        nick.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    var btn = document.getElementById('playh');
                    if (btn) {{
                        btn.scrollIntoView({{ block: 'center' }});
                        btn.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true }}));
                        btn.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true }}));
                        btn.dispatchEvent(new MouseEvent('click', {{ bubbles: true }}));
                    }}
                    if (document.activeElement) document.activeElement.blur();
                """)
                print(f"[Env {self.env_idx}]   JS OK")
            except Exception as e:
                print(f"[Env {self.env_idx}]   JS failed: {type(e).__name__}, trying ActionChains")
                try:
                    nick = self.driver.find_element(By.ID, "nick")
                    ac = ActionChains(self.driver)
                    ac.move_to_element(nick).click().perform()
                    ac.reset_actions()
                    ac.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
                    ac.reset_actions()
                    ac.send_keys(NICKNAME).perform()
                    nick.send_keys(Keys.ENTER)
                    time.sleep(0.1)
                    play_btn = self.driver.find_element(By.ID, "playh")
                    ac.reset_actions()
                    ac.move_to_element(play_btn).click().perform()
                    print(f"[Env {self.env_idx}]   ActionChains OK")
                except Exception as e2:
                    print(f"[Env {self.env_idx}]   ActionChains failed: {type(e2).__name__}")

            # Retry JS click
            try:
                self.driver.execute_script("""
                    var btn = document.getElementById('playh');
                    if (btn) btn.click();
                    if (typeof connect === 'function') connect();
                """)
                print(f"[Env {self.env_idx}]   connect() / play click sent")
            except:
                pass

            # Sofort prüfen: wenn das Menü immer noch da ist, war der JS-Click nicht genug.
            spawn_probe = None
            try:
                spawn_probe = self.driver.execute_script("""
                    var nick = document.getElementById('nick');
                    var playh = document.getElementById('playh');
                    var activeTag = document.activeElement ? document.activeElement.tagName : null;
                    return {
                        nickVisible: !!(nick && nick.style.display !== 'none' && nick.getBoundingClientRect().width > 0),
                        playhVisible: !!(playh && playh.style.display !== 'none' && playh.getBoundingClientRect().width > 0),
                        activeTag: activeTag,
                        url: window.location.href
                    };
                """)
                print(
                    f"[Env {self.env_idx}]   spawn_probe activeTag={spawn_probe.get('activeTag')} "
                    f"nickVisible={spawn_probe.get('nickVisible')} playhVisible={spawn_probe.get('playhVisible')}"
                )
            except Exception as e:
                print(f"[Env {self.env_idx}]   spawn_probe failed: {type(e).__name__}: {e}")

            if not self._is_ingame():
                print(f"[Env {self.env_idx}]   JS spawn did not enter game -> JS retries")

                for retry_round in range(SPAWN_CONFIRM_RETRIES):
                    try:
                        self.driver.execute_script("""
                            var nick = document.getElementById('nick');
                            var btn = document.getElementById('playh');
                            if (nick) {
                                var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                                setter.call(nick, arguments[0]);
                                nick.dispatchEvent(new Event('input', { bubbles: true }));
                                nick.dispatchEvent(new Event('change', { bubbles: true }));
                                nick.blur();
                            }
                            if (btn) {
                                btn.click();
                                btn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
                                btn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true}));
                                btn.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                            }
                            if (typeof connect === 'function') connect();
                            if (document.activeElement) document.activeElement.blur();
                        """, NICKNAME)
                        print(f"[Env {self.env_idx}]   JS retry sent (round {retry_round + 1})")
                    except Exception as e:
                        print(f"[Env {self.env_idx}]   JS retry failed (round {retry_round + 1}): {type(e).__name__}: {e}")

                    time.sleep(SPAWN_CONFIRM_DELAY)
                    if self._is_ingame():
                        print(f"[Env {self.env_idx}]   spawn confirmed in JS retry round {retry_round + 1}")
                        break

            try:
                self.driver.execute_script("window.xm = 100; window.ym = 0;")
            except:
                pass

            self._last_click_time = time.time()
            self._spawn_attempts += 1
            elapsed = time.time() - t0
            print(f"[Env {self.env_idx}] SPAWN_ATTEMPT done in {elapsed:.2f}s")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[Env {self.env_idx}] SPAWN_ERROR: {type(e).__name__}: {e}")

    def _is_ingame(self):
        t0 = time.time()
        try:
            result = self.driver.execute_script("""
                var nick = document.getElementById('nick');
                var playh = document.getElementById('playh');
                var nickVisible = false;
                var playhVisible = false;
                var snakeAlive = false;
                var slitherMatch = false;

                try {
                    nickVisible = !!(nick && nick.style.display !== 'none' && nick.getBoundingClientRect().width > 0);
                } catch(e) {}

                try {
                    playhVisible = !!(playh && playh.style.display !== 'none' && playh.getBoundingClientRect().width > 0);
                } catch(e) {}

                try {
                    if (typeof snake !== 'undefined' && snake !== null && !snake.dead)
                        snakeAlive = true;
                } catch(e) {}

                try {
                    if (typeof slithers !== 'undefined') {
                        for (var k in slithers) {
                            if (slithers[k].nk && slithers[k].nk.trim() === 'Der_Frido' && !slithers[k].dead) {
                                slitherMatch = true;
                                break;
                            }
                        }
                    }
                } catch(e) {}

                return {
                    nickVisible: nickVisible,
                    playhVisible: playhVisible,
                    snakeAlive: snakeAlive,
                    slitherMatch: slitherMatch
                };
            """)
            ingame = bool(result.get("snakeAlive", False) or result.get("slitherMatch", False))
            if self._spawn_wait_steps % 25 == 0 or ingame:
                print(
                    f"[Env {self.env_idx}] INGAME_CHECK nickVisible={result.get('nickVisible')} "
                    f"playhVisible={result.get('playhVisible')} snakeAlive={result.get('snakeAlive')} "
                    f"slitherMatch={result.get('slitherMatch')} -> ingame={ingame}"
                )
            elapsed = time.time() - t0
            if elapsed > 2.0:
                print(f"[Env {self.env_idx}]   _is_ingame SLOW {elapsed:.2f}s")
            return ingame
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[Env {self.env_idx}]   _is_ingame ERROR after {elapsed:.2f}s: {type(e).__name__}: {e}")
            return False

    # ================================================================
    # SCREENSHOT & SPIELZUSTAND
    # ================================================================

    def _get_screenshot(self):
        try:
            b64 = self.driver.get_screenshot_as_base64()
            buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return np.zeros((160, 160, 1), dtype=np.uint8)
            img = cv2.resize(img, (160, 160))
            return np.expand_dims(img, axis=-1)
        except:
            return np.zeros((160, 160, 1), dtype=np.uint8)

    def _get_score(self):
        t0 = time.time()
        try:
            result = self.driver.execute_script("""
                var me = null;
                if (typeof snake !== 'undefined' && snake !== null && !snake.dead) {
                    me = snake;
                } else if (typeof slithers !== 'undefined') {
                    for (var k in slithers) {
                        if (slithers[k].nk && slithers[k].nk.trim() === 'Der_Frido' && !slithers[k].dead) {
                            me = slithers[k]; break;
                        }
                    }
                }
                if (!me || me.dead) return {dead: true, score: 0};
                var score = 0;
                try {
                    score = Math.floor(15 * (fpsls[me.sct] + me.fam / fpsls[me.sct]) - 15);
                } catch(e) {
                    score = me.sct || 0;
                }
                return {dead: false, score: score};
            """)
            dead = result.get("dead", True)
            score = int(result.get("score", 0))
            elapsed = time.time() - t0
            if elapsed > 2.0:
                print(f"[Env {self.env_idx}]   _get_score SLOW {elapsed:.2f}s (dead={dead}, score={score})")
            return max(score, 0), dead
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[Env {self.env_idx}]   _get_score ERROR after {elapsed:.2f}s: {type(e).__name__}: {e}")
            return 0, True

    # ================================================================
    # GYM INTERFACE
    # ================================================================

    def reset(self, seed=None, options=None):
        if self.driver is None:
            self._start_browser()

        print(f"[Env {self.env_idx}] RESET")
        self.last_score = 10
        self.peak_score_this_run = 10
        self.steps_this_run = 0
        self.just_spawned = True
        self.spawn_time = time.time()
        self._spawn_grace_until = 0.0
        self._waiting_for_spawn = True
        self._spawn_attempts = 0
        self._spawn_wait_steps = 0
        self._last_click_time = time.time()
        self._spawn_triggered_after_delay = False

        if not self._initial_spawn_done:
            print(f"[Env {self.env_idx}] INIT_SPAWN")
            self._respawn_ready_at = 0.0
            self._initial_spawn_done = True
        else:
            print(f"[Env {self.env_idx}] RESPAWN_DELAY {RESPAWN_DELAY_SECONDS}s")
            self._respawn_ready_at = time.time() + RESPAWN_DELAY_SECONDS

        return np.zeros((160, 160, 1), dtype=np.uint8), {}

    def step(self, action):
        self.steps_this_run += 1
        BLANK = np.zeros((160, 160, 1), dtype=np.uint8)

        # Spawn-Wartemodus
        if self._waiting_for_spawn:
            self._spawn_wait_steps += 1
            wait_left = self._respawn_ready_at - time.time()

            if wait_left > 0:
                if self._spawn_wait_steps % 50 == 0:
                    print(f"[Env {self.env_idx}] WAIT_SPAWN {wait_left:.1f}s left (step {self._spawn_wait_steps})")
                return BLANK, 0.0, False, False, {}

            # Delay fertig - spawn trigger
            if not self._spawn_triggered_after_delay:
                print(f"[Env {self.env_idx}] SPAWN_TRIGGER")
                self._try_spawn()
                self._spawn_triggered_after_delay = True

            # Timeout check
            if self._spawn_wait_steps > MAX_SPAWN_WAIT_STEPS:
                print(f"[Env {self.env_idx}] SPAWN_TIMEOUT {self._spawn_wait_steps} -> reload")
                self._load_page(first_load=False)
                self._spawn_wait_steps = 0
                self._spawn_attempts = 0
                self._try_spawn()
                return BLANK, 0.0, False, False, {}

            # Check if ingame
            if self._is_ingame():
                self._waiting_for_spawn = False
                self.spawn_time = time.time()
                self._spawn_grace_until = time.time() + SPAWN_GRACE_SECONDS
                self.just_spawned = True
                self._spawn_wait_steps = 0
                print(f"[Env {self.env_idx}] IN_GAME")
            else:
                # Retry alle 3s
                if time.time() - self._last_click_time > 3.0:
                    print(f"[Env {self.env_idx}] RETRY_SPAWN (attempt #{self._spawn_attempts})")
                    self._try_spawn()
                    self._last_click_time = time.time()
                return BLANK, 0.0, False, False, {}

        # Action ausführen
        boost = 1 if action >= 8 else 0
        direction = action % 8
        rad = math.radians(direction * 45)
        r = 600
        ziel_x = int(math.cos(rad) * r)
        ziel_y = int(math.sin(rad) * r)

        try:
            t = time.time()
            self.driver.execute_script(f"window.xm = {ziel_x}; window.ym = {ziel_y};")
            t_elapsed = time.time() - t
            if t_elapsed > 1.0:
                print(f"[Env {self.env_idx}] SCRIPT_SLOW {t_elapsed:.2f}s")
            
            if boost:
                self.driver.execute_script(
                    "document.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true, keyCode:32, key:' ', code:'Space'}));"
                )
            else:
                self.driver.execute_script(
                    "document.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, keyCode:32, key:' ', code:'Space'}));"
                )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[Env {self.env_idx}] ACTION_ERROR: {type(e).__name__}: {e}")
            return self._get_screenshot(), -50.0, True, False, {}

        obs = self._get_screenshot()
        current_score, dead = self._get_score()

        if dead and time.time() < self._spawn_grace_until:
            grace_left = self._spawn_grace_until - time.time()
            print(f"[Env {self.env_idx}] DEATH_IGNORED during spawn grace ({grace_left:.1f}s left)")
            dead = False

        if dead:
            alive_seconds = time.time() - self.spawn_time if self.spawn_time else 999
            if self.peak_score_this_run > 30 and alive_seconds < MIN_ALIVE_SECONDS:
                penalty_factor = 1.0 - (alive_seconds / MIN_ALIVE_SECONDS)
                reward = -50.0 + (-80.0 * penalty_factor)
            else:
                reward = -50.0

            print(f"[Env {self.env_idx}] DEAD (alive={alive_seconds:.1f}s)")
            self._waiting_for_spawn = True
            self._spawn_attempts = 0
            self._spawn_wait_steps = 0
            self._respawn_ready_at = time.time() + RESPAWN_DELAY_SECONDS

        else:
            if self.just_spawned:
                self.last_score = max(current_score, 10)
                self.peak_score_this_run = self.last_score
                self.just_spawned = False
                reward = 0.0
            else:
                score_diff = current_score - self.last_score

                if self.last_score > 20 and current_score < self.last_score - 20:
                    self.last_score = current_score
                    self._waiting_for_spawn = True
                    self._spawn_attempts = 0
                    self._spawn_wait_steps = 0
                    self._respawn_ready_at = time.time() + RESPAWN_DELAY_SECONDS
                    print(f"[Env {self.env_idx}] LOST_MASS")
                    return obs, -100.0, True, False, {}

                if score_diff > 0:
                    new_peak_diff = max(0, current_score - self.peak_score_this_run)
                    if new_peak_diff > 0:
                        reward = new_peak_diff * (8.0 if boost else 4.0)
                        self.peak_score_this_run = current_score
                    else:
                        reward = score_diff * 0.5
                elif score_diff < 0:
                    reward = -0.5 if boost else -0.1
                else:
                    reward = -0.2 if boost else 0.1

                self.last_score = current_score

        return obs, reward, dead, False, {}

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        try:
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        except Exception:
            pass
