"""
TCI Website Scraper - Trip Closing Details
Har trip individual row ke roop mein scrape karta hai (no grouping).
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time, datetime


def get_driver():
    opts = webdriver.ChromeOptions()
    opts.binary_location = "/usr/bin/chromium"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--start-maximized")
    return webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"), options=opts)


# Is JS helper mein poora "supplier radio dhoondo aur select karo" logic hai.
# PURANA BUG: sirf radio ke value/id attribute mein keyword ("supplier")
# dhoondte the. Asli TCI login page ke radio buttons mein value aksar sirf
# "0"/"1" jaisa hota hai aur <label for="..."> bhi nahi hota — radio ke baad
# seedha plain text likha hota hai ("Employee"/"Supplier", bina label tag ke).
# Isi wajah se purana match kabhi hota hi nahi tha, aur Employee (default)
# hi selected reh jaata tha, chahe kitni bhi baar retry karo — isliye Subhita
# ke case mein bhi sirf tabhi kaam hua jab manually click kiya gaya.
#
# Naya logic teen tareeke se text dhoondta hai:
#   1. <label for="radio-id">
#   2. radio khud kisi <label> ke andar wrapped ho
#   3. radio ke turant baad wala plain text (sibling text node) — yehi
#      asli TCI site ka pattern hai
# Agar phir bhi "supplier" text kahin na mile, fallback: jo radio default
# checked NAHI hai use select kar deta hai (group mein sirf 2 hi option
# hote hain — Employee aur Supplier).
_SELECT_SUPPLIER_JS = r"""
function labelTextFor(radio) {
    var text = '';
    if (radio.id) {
        var lbl = document.querySelector("label[for='" + radio.id + "']");
        if (lbl) text += ' ' + lbl.innerText;
    }
    var wrap = radio.closest ? radio.closest('label') : null;
    if (wrap) text += ' ' + wrap.innerText;
    var node = radio.nextSibling;
    var guard = 0;
    while (node && guard < 6) {
        if (node.nodeType === 3) {
            text += ' ' + node.textContent;
        } else if (node.nodeType === 1) {
            if (node.tagName === 'INPUT' || node.tagName === 'BR') break;
            text += ' ' + (node.innerText || node.textContent || '');
        }
        node = node.nextSibling;
        guard++;
    }
    text += ' ' + (radio.value || '') + ' ' + (radio.id || '') + ' ' + (radio.name || '');
    return text.toLowerCase();
}

function run(mode) {
    var radios = Array.prototype.slice.call(document.querySelectorAll("input[type='radio']"));
    if (!radios.length) return 'no_radios';

    var groups = {};
    radios.forEach(function (r) {
        var key = r.name || '__noname__';
        (groups[key] = groups[key] || []).push(r);
    });

    var candidateGroup = radios;
    for (var key in groups) {
        var joined = groups[key].map(labelTextFor).join(' | ');
        if (joined.indexOf('supplier') !== -1 || joined.indexOf('employee') !== -1) {
            candidateGroup = groups[key];
            break;
        }
    }

    if (mode === 'check') {
        for (var i = 0; i < candidateGroup.length; i++) {
            if (labelTextFor(candidateGroup[i]).indexOf('supplier') !== -1 && candidateGroup[i].checked) {
                return 'selected';
            }
        }
        return 'not_selected';
    }

    radios.forEach(function (r) { r.removeAttribute('data-tci-target'); });

    for (var i = 0; i < candidateGroup.length; i++) {
        var r = candidateGroup[i];
        if (labelTextFor(r).indexOf('supplier') !== -1) {
            r.checked = true;
            r.setAttribute('data-tci-target', '1');
            r.dispatchEvent(new Event('change', {bubbles: true}));
            r.dispatchEvent(new Event('click', {bubbles: true}));
            return 'text_match';
        }
    }

    if (candidateGroup.length === 2) {
        var target = null;
        for (var j = 0; j < candidateGroup.length; j++) {
            if (!candidateGroup[j].checked) { target = candidateGroup[j]; break; }
        }
        if (!target) target = candidateGroup[1];
        target.checked = true;
        target.setAttribute('data-tci-target', '1');
        target.dispatchEvent(new Event('change', {bubbles: true}));
        target.dispatchEvent(new Event('click', {bubbles: true}));
        return 'fallback_complement';
    }

    return 'not_found';
}
return run(arguments[0]);
"""


def click_radio(driver, keyword="SUPPLIER", max_retries=8):
    def is_target_selected():
        try:
            return driver.execute_script(_SELECT_SUPPLIER_JS, 'check') == 'selected'
        except Exception:
            return False

    for attempt in range(max_retries):
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='radio']"))
            )
        except Exception:
            pass

        if is_target_selected():
            return True

        try:
            driver.execute_script(_SELECT_SUPPLIER_JS, 'select')
        except Exception:
            pass
        time.sleep(0.5)

        if is_target_selected():
            return True

        try:
            targets = driver.find_elements(By.XPATH, "//input[@type='radio'][@data-tci-target='1']")
            for r in targets:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                time.sleep(0.15)
                try:
                    r.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", r)
                time.sleep(0.25)
        except Exception:
            pass

        time.sleep(0.5)
        if is_target_selected():
            return True

        time.sleep(0.6)

    return is_target_selected()


def _fill_and_select_supplier(driver, username, password):
    driver.get("https://tciexpressemployee.in/myexpress.asp")
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass
    time.sleep(1.5)

    try:
        user_field = driver.find_element(By.XPATH,
            "//input[contains(@name,'user') or contains(@id,'user') or contains(@name,'User') or contains(@id,'User')]")
        user_field.clear()
        user_field.send_keys(username)
    except Exception:
        pass

    try:
        pass_field = driver.find_element(By.XPATH,
            "//input[@type='password']")
        pass_field.clear()
        pass_field.send_keys(password)
    except Exception:
        pass

    return click_radio(driver, max_retries=2)


def login(driver, username, password, max_login_attempts=3):
    supplier_ok = False
    for attempt in range(1, max_login_attempts + 1):
        supplier_ok = _fill_and_select_supplier(driver, username, password)
        if supplier_ok:
            print(f"  ✓ SUPPLIER radio select ho gaya (attempt {attempt})")
            break
        print(f"  ⚠ SUPPLIER radio select nahi hua (attempt {attempt}/{max_login_attempts}) — retry karte hain...")
        time.sleep(1.5)

    if not supplier_ok:
        print("  ❌ SUPPLIER radio select NAHI ho paaya — login galat account type se ho sakta tha!")
        try:
            driver.save_screenshot(f"debug_login_{username}.png")
            with open(f"debug_login_{username}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception:
            pass
        raise RuntimeError(
            f"SUPPLIER radio select nahi ho paaya ({username}), {max_login_attempts} attempts ke baad bhi. "
            "Login is liye rok diya — Employee ke saath login galat hota."
        )

    if not click_radio(driver, max_retries=2):
        raise RuntimeError(
            f"SUPPLIER radio submit se theek pehle unselect ho gaya ({username}). "
            "Login is liye rok diya."
        )

    time.sleep(0.5)
    btn = driver.find_element(By.XPATH,
        "//input[@type='submit'] | //button[contains(translate(text(),'login','LOGIN'),'LOGIN')]")
    btn.click()
    time.sleep(4)


def n(s):
    try:
        return float(str(s).replace(',', '').strip())
    except:
        return 0.0


def scrape_account_trips(username, password, from_date, to_date):
    driver = get_driver()
    trips = []

    try:
        login(driver, username, password)

        found_link = False
        for txt in ["6. Trip Closing Detail", "Trip Closing Detail", "Trip Closing"]:
            try:
                link = driver.find_element(By.XPATH, f"//*[contains(text(),'{txt}')]")
                driver.execute_script("arguments[0].click();", link)
                time.sleep(3)
                found_link = True
                break
            except: pass

        if not found_link:
            print("  ⚠ 'Trip Closing Detail' link nahi mila")
            driver.save_screenshot(f"trip_link_error_{username}.png")
            return []

        time.sleep(2)
        date_inputs = driver.find_elements(By.XPATH, "//input[@type='text']")
        if len(date_inputs) >= 2:
            fi = date_inputs[0]
            driver.execute_script("arguments[0].value='';", fi)
            fi.click(); time.sleep(0.3)
            fi.send_keys(from_date); time.sleep(0.3)
            fi.send_keys(Keys.TAB); time.sleep(0.8)

            ti = date_inputs[1]
            driver.execute_script("arguments[0].value='';", ti)
            ti.click(); time.sleep(0.3)
            ti.send_keys(to_date); time.sleep(0.3)
            ti.send_keys(Keys.TAB); time.sleep(0.8)
        else:
            print(f"  ⚠ Date fields nahi mile ({len(date_inputs)} mile)")

        try:
            show = driver.find_element(By.XPATH,
                "//input[@value='Show' or @value='show'] | //button[contains(text(),'Show')]")
            show.click(); time.sleep(2)
        except:
            print("  ⚠ Show button nahi mila")

        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert.accept()
            time.sleep(4)
        except:
            pass

        time.sleep(3)

        tables = driver.find_elements(By.TAG_NAME, "table")
        data_table = None
        for table in tables:
            text = table.text.upper()
            if "VEHICLE" in text and "TCS" in text and "LIABILITY" in text:
                data_table = table
                break

        if not data_table:
            print(f"  ⚠ Data table nahi mila")
            driver.save_screenshot(f"trip_table_error_{username}.png")
            return []

        rows = data_table.find_elements(By.TAG_NAME, "tr")

        headers = []
        for row in rows[:3]:
            cells = [c.text.strip().upper().replace('\n', ' ')
                     for c in row.find_elements(By.XPATH, ".//th|.//td")]
            if "VEHICLE" in ' '.join(cells):
                headers = cells
                break

        def ci(keys):
            for k in keys:
                for i, h in enumerate(headers):
                    if k in h: return i
            return -1

        veh_col      = ci(["VEHICLE NO", "VEHICLE"])
        tcsno_col    = ci(["TCS NO"])
        branch_col   = ci(["TCS BRANCH", "BRANCH"])
        tcsdate_col  = ci(["TCS DATE"])
        dest_col     = ci(["TCS DEST", "DEST"])
        close_col    = ci(["TCS CLOSE DATE", "CLOSE DATE"])
        liab_col     = ci(["LIABILITY AMOUNT", "LIABILITY"])
        gst_col      = ci(["GST AMOUNT", "GST"])
        netliab_col  = ci(["NET LIABILITY", "NET LIABILITY AMOUNT"])
        penalty_col  = ci(["PENALTY DEDUCTED", "PENALTY"])
        handling_col = ci(["HANDLING AMOUNT", "HANDLING"])
        early_col    = ci(["EARLY PAYMENT", "EARLY"])
        gps_col      = ci(["GPS AMOUNT", "GPS"])
        tds_col      = ci(["TDS DEDUCTION", "TDS"])

        for row in rows[1:]:
            cells = [td.text.strip()
                     for td in row.find_elements(By.TAG_NAME, "td")]
            if len(cells) < 5:
                continue

            def g(idx):
                return cells[idx].strip() if 0 <= idx < len(cells) else ""

            vehicle = g(veh_col)
            if not vehicle:
                continue
            if vehicle.upper() in ["VEHICLE NO", "SR NO", "SR", "#"]:
                continue

            trips.append({
                'vehicle'    : vehicle,
                'tcs_no'     : g(tcsno_col),
                'tcs_branch' : g(branch_col),
                'tcs_date'   : g(tcsdate_col),
                'tcs_dest'   : g(dest_col),
                'close_date' : g(close_col),
                'liability'  : n(g(liab_col)),
                'gst_amt'    : n(g(gst_col)),
                'net_liability': n(g(netliab_col)),
                'penalty'    : n(g(penalty_col)),
                'handling'   : n(g(handling_col)),
                'early_ded'  : n(g(early_col)),
                'gps_ded'    : n(g(gps_col)),
                'tds_ded'    : n(g(tds_col)),
            })

    except Exception as e:
        print(f"  Scrape error: {e}")
        try:
            driver.save_screenshot(f"debug_{username}.png")
            with open(f"debug_{username}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception:
            pass
    finally:
        driver.quit()

    print(f"  {len(trips)} trips found (individual rows)")
    return trips


def scrape_all_accounts(accounts, from_date, to_date):
    results = {}
    for acc_code, acc_info in accounts.items():
        print(f"\nScraping {acc_info['name']} ({from_date} to {to_date})...")
        try:
            trips = scrape_account_trips(
                acc_info['username'], acc_info['password'],
                from_date, to_date)
            results[acc_code] = trips
        except Exception as e:
            print(f"  Error: {e}")
            results[acc_code] = []
    return results
