from selenium import webdriver
from selenium.webdriver.edge.options import Options
import time

options = Options()
options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
options.add_argument("--ignore-certificate-errors")
options.add_argument("--window-size=800,600")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])

driver = webdriver.Edge(options=options)
driver.get("http://slither.com/io")
time.sleep(8)

driver.execute_script("""
    var nick = document.getElementById('nick');
    if (nick) nick.value = 'KI_Snake';
    if (typeof connect === 'function') connect();
""")
print("Warte 5s auf Spawn...")
time.sleep(5)

for i in range(20):
    time.sleep(1)
    result = driver.execute_script("""
        // Eigene Schlange per Nickname finden
        var me = null;
        if (typeof slithers !== 'undefined') {
            for (var k in slithers) {
                if (slithers[k].nk && slithers[k].nk.trim() === 'KI_Snake') {
                    me = slithers[k];
                    break;
                }
            }
            // Fallback: kleinste ID (frisch gespawnt)
            if (!me) {
                for (var k in slithers) {
                    if (!me || slithers[k].sct < me.sct) me = slithers[k];
                }
            }
        }
        
        if (!me) return {error: 'keine schlange gefunden'};
        
        // Score berechnen
        var score_raw = 0;
        try {
            score_raw = Math.floor(15 * (fpsls[me.sct] + me.fam / fpsls[me.sct]) - 15);
        } catch(e) { score_raw = -1; }
        
        // fpsls Werte anschauen
        var fpsls_sample = [];
        for (var i = 0; i < 5; i++) fpsls_sample.push(fpsls[i]);
        
        return {
            nk: me.nk,
            sct: me.sct,
            fam: me.fam,
            dead: me.dead,
            score_raw: score_raw,
            fpsls_sample: fpsls_sample,
            // Rohwert: sct ist der Score-Index
            score_simple: me.sct
        };
    """)
    print(f"[{i}s] {result}")

input("Enter...")
driver.quit()