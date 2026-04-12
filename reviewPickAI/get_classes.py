import asyncio
from playwright.async_api import async_playwright

async def run_crawler(url):
    async with async_playwright() as p:
        # 차단을 우회하기 위해 Headless 모드를 해제하고 브라우저를 직접 엽니다.
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        
        # 일반 사용자의 User-Agent와 Viewport를 설정합니다.
        context = await browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("1. 페이지 진입 중...")
        await page.goto(url, wait_until="domcontentloaded")
        # 접속 후 봇 차단 화면 대기를 위해 약간 기다려줍니다.
        await page.wait_for_timeout(3000)

        print("2. 상품평 탭으로 이동 및 클릭 중...")
        # 리뷰 탭 선택자. Playwright의 click()은 자동으로 요소를 향해 스크롤해줍니다.
        review_tab = page.locator('[data-tab="review"]')
        await review_tab.scroll_into_view_if_needed()
        await review_tab.click()
        
        # 리뷰 데이터가 네트워크에서 로드될 때까지 명시적으로 기다립니다.
        await page.wait_for_timeout(2500)
        
        print("3. 최신순 버튼 클릭 중...")
        latest_btn = page.locator('.sdp-review__article__order__list [data-order="RECENT"]')
        # 혹시 화면에 안 보인다면 조금 스크롤합니다.
        await latest_btn.scroll_into_view_if_needed()
        await latest_btn.click()
        
        # 최신순 정렬 후 데이터를 다시 로드하는 과정을 기다립니다.
        await page.wait_for_timeout(2500)

        print("4. 순수 텍스트 리뷰만 추출 중...")
        # 이름, 별점, 이미지가 아닌 '리뷰 본문'만을 포함하는 컨테이너 선택자입니다.
        review_locators = page.locator('.sdp-review__article__list__review__content')
        
        # 모든 항목의 내부 텍스트만 추출
        review_contents = await review_locators.all_inner_texts()
        
        # 빈 값 정리
        extracted_texts = [text.strip() for text in review_contents if text.strip()]
        
        for idx, text in enumerate(extracted_texts, 1):
            print(f"\n[리뷰 {idx}]")
            print(text)

        print(f"\n=> 총 {len(extracted_texts)}개의 텍스트 리뷰를 성공적으로 가져왔습니다.")
        
        # 브라우저 종료 여부 (디버그할 때는 주석 처리해서 결과를 볼 수 있습니다)
        await browser.close()
        
        return extracted_texts

if __name__ == "__main__":
    # 사용자님이 주셨던 테스트 URL
    test_url = "https://www.coupang.com/vp/products/8723409509?vendorItemId=92335485176"
    asyncio.run(run_crawler(test_url))
