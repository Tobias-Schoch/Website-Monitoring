#!/usr/bin/env python3
"""
API-based Diff Tester - Tests semantic HTML change filtering via API.

Usage:
    python3 test_diff_api.py [--url http://localhost:8000]
"""

import requests
import json
import sys
from typing import Dict, Any, Optional


class DiffTesterAPI:
    """API client for testing HTML diff detection."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.test_results = []

    def test_diff(
        self,
        original_html: str,
        new_html: str,
        test_name: str = "Unnamed Test"
    ) -> Dict[str, Any]:
        """
        Call the test-diff API endpoint.

        Args:
            original_html: Original HTML content
            new_html: New HTML content
            test_name: Name of this test case

        Returns:
            API response as dict
        """
        url = f"{self.base_url}/api/test-diff"
        payload = {
            "original_html": original_html,
            "new_html": new_html
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()

            self.test_results.append({
                "name": test_name,
                "success": True,
                "result": result
            })

            return result

        except requests.exceptions.RequestException as e:
            error_result = {
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }
            self.test_results.append({
                "name": test_name,
                "success": False,
                "result": error_result
            })
            return error_result

    def assert_no_change(
        self,
        result: Dict[str, Any],
        test_name: str
    ) -> bool:
        """Assert that no change was detected."""
        if result.get("has_changed") == False:
            print(f"✅ {test_name}: No change detected (as expected)")
            return True
        else:
            print(f"❌ {test_name}: Change detected (expected no change!)")
            print(f"   Description: {result.get('description', 'N/A')}")
            if result.get('diff'):
                print(f"   Diff preview: {result['diff'][:200]}...")
            return False

    def assert_change(
        self,
        result: Dict[str, Any],
        test_name: str,
        expected_type: Optional[str] = None,
        expected_priority: Optional[str] = None
    ) -> bool:
        """Assert that a change was detected with optional type/priority check."""
        if not result.get("has_changed"):
            print(f"❌ {test_name}: No change detected (expected change!)")
            return False

        success = True
        print(f"✅ {test_name}: Change detected")

        if expected_type and result.get("type") != expected_type:
            print(f"   ⚠️  Type mismatch: got '{result.get('type')}', expected '{expected_type}'")
            success = False

        if expected_priority and result.get("priority") != expected_priority:
            print(f"   ⚠️  Priority mismatch: got '{result.get('priority')}', expected '{expected_priority}'")
            success = False

        print(f"   Type: {result.get('type', 'N/A')}")
        print(f"   Priority: {result.get('priority', 'N/A')}")
        print(f"   Description: {result.get('description', 'N/A')}")

        return success

    def print_summary(self):
        """Print test summary."""
        total = len(self.test_results)
        success = sum(1 for r in self.test_results if r["success"])

        print("\n" + "="*70)
        print(f"TEST SUMMARY: {success}/{total} tests successful")
        print("="*70)


def run_all_tests(api_url: str = "http://localhost:8000"):
    """Run all test cases."""
    tester = DiffTesterAPI(api_url)

    print(f"🧪 Testing Diff API at: {api_url}")
    print("="*70)

    # ===================================================================
    # Test 1: CCM Cookie Banner (should be filtered)
    # ===================================================================
    print("\n📋 Test Category: CCM Cookie Banner Filtering")
    print("-"*70)

    original = """
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>Welcome</h1>
        <p>This is the main content.</p>
    </body>
    </html>
    """

    new_with_ccm = """
    <html>
    <head>
        <title>Test</title>
        <script src="https://ccm.example.com/script.js"></script>
    </head>
    <body>
        <div class="ccm-banner" data-ccm-id="12345">
            <p>Cookie Consent Manager</p>
            <button>Accept</button>
        </div>
        <h1>Welcome</h1>
        <p>This is the main content.</p>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_with_ccm, "CCM Banner Added")
    tester.assert_no_change(result, "CCM Banner Added")

    # ===================================================================
    # Test 2: Dynamic Attributes (should be filtered)
    # ===================================================================
    print("\n📋 Test Category: Dynamic Attributes Filtering")
    print("-"*70)

    original = """
    <html>
    <body>
        <div class="container">
            <h1 id="title">Hello World</h1>
            <p data-id="123">Content here</p>
        </div>
    </body>
    </html>
    """

    new_attrs = """
    <html>
    <body>
        <div class="container-v2 dynamic-456">
            <h1 id="title-789" style="color: red;">Hello World</h1>
            <p data-id="999" aria-label="test">Content here</p>
        </div>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_attrs, "Dynamic Attributes Changed")
    tester.assert_no_change(result, "Dynamic Attributes Changed")

    # ===================================================================
    # Test 3: Whitespace/Formatting Changes (should be filtered)
    # ===================================================================
    print("\n📋 Test Category: Whitespace/Formatting Filtering")
    print("-"*70)

    original = """
    <html><body><h1>Title</h1><p>Text</p></body></html>
    """

    new_formatted = """
    <html>
        <body>
            <h1>Title</h1>
            <p>Text</p>
        </body>
    </html>
    """

    result = tester.test_diff(original, new_formatted, "Whitespace/Formatting Changed")
    tester.assert_no_change(result, "Whitespace/Formatting Changed")

    # ===================================================================
    # Test 4: Real Text Change (should be detected)
    # ===================================================================
    print("\n📋 Test Category: Real Content Changes")
    print("-"*70)

    original = """
    <html>
    <body>
        <h1>Welcome</h1>
        <p>Old text content</p>
    </body>
    </html>
    """

    new_text = """
    <html>
    <body>
        <h1>Welcome</h1>
        <p>New text content</p>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_text, "Text Content Changed")
    tester.assert_change(result, "Text Content Changed", expected_type="CONTENT")

    # ===================================================================
    # Test 5: Image Added (should be detected)
    # ===================================================================
    print("\n📋 Test Category: Image Changes")
    print("-"*70)

    original = """
    <html>
    <body>
        <h1>Gallery</h1>
    </body>
    </html>
    """

    new_image = """
    <html>
    <body>
        <h1>Gallery</h1>
        <img src="/photos/boat.jpg" alt="Beautiful Boat">
    </body>
    </html>
    """

    result = tester.test_diff(original, new_image, "Image Added")
    tester.assert_change(result, "Image Added", expected_type="CONTENT")

    # ===================================================================
    # Test 6: Link Added (should be detected)
    # ===================================================================
    print("\n📋 Test Category: Link Changes")
    print("-"*70)

    original = """
    <html>
    <body>
        <h1>Links</h1>
    </body>
    </html>
    """

    new_link = """
    <html>
    <body>
        <h1>Links</h1>
        <a href="/registration">Register Now</a>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_link, "Link Added")
    tester.assert_change(result, "Link Added", expected_type="CONTENT")

    # ===================================================================
    # Test 7: Form Added (should be CRITICAL)
    # ===================================================================
    print("\n📋 Test Category: Form Detection")
    print("-"*70)

    original = """
    <html>
    <body>
        <h1>Warteliste</h1>
        <p>Anmeldung noch nicht möglich</p>
    </body>
    </html>
    """

    new_form = """
    <html>
    <body>
        <h1>Warteliste</h1>
        <p>Anmeldung jetzt möglich!</p>
        <form action="/register" method="post">
            <input type="text" name="name" placeholder="Name">
            <input type="email" name="email" placeholder="Email">
            <button type="submit">Anmelden</button>
        </form>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_form, "Registration Form Added")
    tester.assert_change(result, "Registration Form Added", expected_type="FORM", expected_priority="CRITICAL")

    # ===================================================================
    # Test 8: Critical Keyword Added (should be CRITICAL)
    # ===================================================================
    print("\n📋 Test Category: Keyword Detection")
    print("-"*70)

    original = """
    <html>
    <body>
        <h1>Bootsliegeplatz</h1>
        <p>Informationen folgen</p>
    </body>
    </html>
    """

    new_keyword = """
    <html>
    <body>
        <h1>Bootsliegeplatz</h1>
        <p>Warteliste öffnet bald! Jetzt anmelden!</p>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_keyword, "Critical Keywords Added")
    tester.assert_change(result, "Critical Keywords Added", expected_priority="CRITICAL")

    # ===================================================================
    # Test 9: No Change at All
    # ===================================================================
    print("\n📋 Test Category: Identical Content")
    print("-"*70)

    original = """
    <html>
    <body>
        <h1>Test</h1>
        <p>Same content</p>
    </body>
    </html>
    """

    same = """
    <html>
    <body>
        <h1>Test</h1>
        <p>Same content</p>
    </body>
    </html>
    """

    result = tester.test_diff(original, same, "Identical HTML")
    tester.assert_no_change(result, "Identical HTML")

    # ===================================================================
    # Test 10: Complex Real-World Example
    # ===================================================================
    print("\n📋 Test Category: Real-World Scenario")
    print("-"*70)

    original = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Konstanz Bootsliegeplatz</title>
        <script src="/analytics.js?v=1.2.3"></script>
        <link rel="stylesheet" href="/styles.css?hash=abc123">
    </head>
    <body>
        <div class="ccm-wrapper" data-ccm-timestamp="1234567890">
            <div class="cookie-banner">Cookie Consent</div>
        </div>
        <header class="nav-v1" id="header-123">
            <h1>Bootsliegeplatz Konstanz</h1>
        </header>
        <main>
            <p>Die Warteliste ist derzeit geschlossen.</p>
            <p>Stand: 14.02.2024 10:30 Uhr</p>
        </main>
    </body>
    </html>
    """

    new_real = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Konstanz Bootsliegeplatz</title>
        <script src="/analytics.js?v=1.2.4"></script>
        <link rel="stylesheet" href="/styles.css?hash=xyz789">
    </head>
    <body>
        <div class="ccm-wrapper-v2" data-ccm-timestamp="9876543210">
            <div class="cookie-banner updated">Cookie Consent Manager</div>
        </div>
        <header class="nav-v2" id="header-456" style="color: blue;">
            <h1>Bootsliegeplatz Konstanz</h1>
        </header>
        <main>
            <p>Die Warteliste öffnet am 15.02.2024!</p>
            <p>Stand: 14.02.2024 15:45 Uhr</p>
            <a href="/warteliste">Zur Anmeldung</a>
        </main>
    </body>
    </html>
    """

    result = tester.test_diff(original, new_real, "Real-World: Waitlist Opens")
    tester.assert_change(result, "Real-World: Waitlist Opens", expected_priority="CRITICAL")

    # Print final summary
    tester.print_summary()

    return tester


def run_realworld_tests(api_url: str = "http://localhost:8000"):
    """Run real-world test cases from Konstanz website."""
    tester = DiffTesterAPI(api_url)

    print(f"\n{'='*70}")
    print(f"🌐 REAL-WORLD TEST CASES - Konstanz Website")
    print(f"{'='*70}")

    # ===================================================================
    # Test Case 1: Anker-Tags und IDs
    # ===================================================================
    print("\n📋 Test 1: Anker-Tags und IDs")
    print("-"*70)

    original_1 = """
    <div class="composedcontent-dvv-row subcolumns linearize-level-2" id="row_19056">
        <div class="subcl">
            <h2 class="basecontent-sub-heading">Weitere Angebote</h2>
        </div>
    </div>
    """

    new_1 = """
    <a id="anker19056"></a>
    <div class="composedcontent-dvv-row subcolumns linearize-level-2" id="row_19056">
        <div class="subcl"><a id="anker19057"></a>
            <h2 class="basecontent-sub-heading" id="anker19060">Weitere Angebote</h2>
        </div>
    </div>
    """

    result = tester.test_diff(original_1, new_1, "Anker-Tags hinzugefügt")
    tester.assert_no_change(result, "Anker-Tags hinzugefügt")

    # ===================================================================
    # Test Case 2: CSS-Klassen geändert
    # ===================================================================
    print("\n📋 Test 2: CSS-Klassen geändert")
    print("-"*70)

    original_2 = """
    <div class="richMenuNew" style="">
        <div class="richMenuItem active" style="">
            Content
        </div>
    </div>
    """

    new_2 = """
    <div class="richMenuNew">
        <div class="richMenuItem">
            Content
        </div>
    </div>
    """

    result = tester.test_diff(original_2, new_2, "CSS-Klassen geändert")
    tester.assert_no_change(result, "CSS-Klassen geändert")

    # ===================================================================
    # Test Case 3: externerLink Klasse zu Links
    # ===================================================================
    print("\n📋 Test 3: externerLink Klasse")
    print("-"*70)

    original_3 = """
    <div class="mm-footer-links">
        <a href="https://konstanz.de/impressum" title="Impressum" target="_blank">Impressum</a> |
        <a href="https://konstanz.de/datenschutz" title="Datenschutz" target="_blank">Datenschutz</a>
    </div>
    """

    new_3 = """
    <div class="mm-footer-links">
        <a href="https://konstanz.de/impressum" title="Impressum" target="_blank" class="externerLink">Impressum</a> |
        <a href="https://konstanz.de/datenschutz" title="Datenschutz" target="_blank" class="externerLink">Datenschutz</a>
    </div>
    """

    result = tester.test_diff(original_3, new_3, "externerLink hinzugefügt")
    tester.assert_no_change(result, "externerLink hinzugefügt")

    # ===================================================================
    # Test Case 4: CCM Cookie Banner komplett
    # ===================================================================
    print("\n📋 Test 4: CCM Cookie Banner")
    print("-"*70)

    original_4 = """
    <html>
    <body>
        <h1>Bootsliegeplatz</h1>
        <p>Informationen zur Warteliste</p>
    </body>
    </html>
    """

    new_4 = """
    <html>
    <body>
        <noscript data-ccm-orig-inert="0" inert="">
            <img alt="" src="https://statistik.komm.one/matomo/piwik.php?idsite=12">
        </noscript>
        <div class="mm-page__blocker mm-slideout" data-ccm-orig-inert="0" inert=""></div>
        <div class="ccm-root">
            <div id="ccm-widget" class="ccm-modal ccm-widget instapager_ignore ccm--is-blocking">
                <div class="ccm-modal-inner">
                    <div class="ccm-modal--header">
                        <button type="button" class="ccm-dismiss-button">Schließen</button>
                    </div>
                    <div class="ccm-modal--body">
                        <div class="ccm-widget--title">Wir nutzen Cookies und andere Technologien.</div>
                        <div class="ccm-widget--introduction">
                            <p>Diese Website nutzt Cookies und vergleichbare Funktionen zur Verarbeitung von
                            Endgeräteinformationen und personenbezogenen Daten. Die Verarbeitung dient der
                            Einbindung von Inhalten, externen Diensten und Elementen Dritter, der statistischen
                            Analyse/Messung, der personalisierten Werbung sowie der Einbindung sozialer Medien.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <h1>Bootsliegeplatz</h1>
        <p>Informationen zur Warteliste</p>
    </body>
    </html>
    """

    result = tester.test_diff(original_4, new_4, "CCM Banner hinzugefügt")
    tester.assert_no_change(result, "CCM Banner hinzugefügt")

    # ===================================================================
    # Test Case 5: Kombination aller Änderungen
    # ===================================================================
    print("\n📋 Test 5: Kombination aller Änderungen")
    print("-"*70)

    original_5 = """
    <div class="container" id="main">
        <h1>Bootsliegeplatz Konstanz</h1>
        <div class="menu">
            <a href="/impressum">Impressum</a>
        </div>
    </div>
    """

    new_5 = """
    <a id="anker-top"></a>
    <div class="container-v2" id="main-123" style="padding: 20px;">
        <div class="ccm-banner" data-ccm-id="xyz">Cookie Notice</div>
        <h1 class="title-new" id="anker-h1">Bootsliegeplatz Konstanz</h1>
        <div class="menu active" style="display: block;">
            <a href="/impressum" class="externerLink" target="_blank">Impressum</a>
        </div>
    </div>
    """

    result = tester.test_diff(original_5, new_5, "Alle strukturellen Änderungen")
    tester.assert_no_change(result, "Alle strukturellen Änderungen")

    # Print summary
    tester.print_summary()

    return tester


if __name__ == "__main__":
    # Get API URL from command line or use default
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    try:
        # Run standard tests
        print("Running standard tests...")
        tester1 = run_all_tests(api_url)

        # Run real-world tests
        print("\n\nRunning real-world tests...")
        tester2 = run_realworld_tests(api_url)

        # Calculate combined results
        total_tests = len(tester1.test_results) + len(tester2.test_results)
        total_failed = (
            sum(1 for r in tester1.test_results if not r["success"]) +
            sum(1 for r in tester2.test_results if not r["success"])
        )

        print(f"\n\n{'='*70}")
        print(f"🏁 FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"Total tests: {total_tests}")
        print(f"Standard tests: {len(tester1.test_results)}")
        print(f"Real-world tests: {len(tester2.test_results)}")
        print(f"Failed: {total_failed}")
        print(f"Success rate: {((total_tests - total_failed) / total_tests * 100):.1f}%")
        print(f"{'='*70}")

        # Exit with error code if any test failed
        sys.exit(0 if total_failed == 0 else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
