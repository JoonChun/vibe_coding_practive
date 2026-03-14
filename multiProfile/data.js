const globalData = {
    "profile": {
        "image": "assets/profile.png",
        "title": "vi.joon",
        "description": "AI와 감성으로 완성하는 프로젝트 아카이브"
    },
    "featured": {
        "title": "이제 시작하는 바이브 코딩 프로젝트✨",
        "link": "./guide/index.html",
        "isActive": true
    },
    "projects": [
        {
            "id": "proj-3",
            "title": "AI Vibe 코딩 연습",
            "description": "Antigravity 메인으로 사용",
            "tags": [
                "Gemini",
                "Antigravity",
                "Claude"
            ],
            "url": "https://github.com/JoonChun/vibe_coding_practive",
            "thumbnail": "https://via.placeholder.com/600x400/2C2F33/FFFFFF?text=Vibe+Dashboard"
        }
    ],
    "socials": {
        "instagram": "https://www.instagram.com/vi.jooncoding/",
        "github": "https://github.com/JoonChun",
        "email": "mailto:jeonjun47@gmail.com"
    }
};

// --- LocalStorage Persistence Layer ---
// 어드민 패널에서 수정한 데이터가 있다면 소스 코드의 기본값 대신 사용합니다.
const savedData = localStorage.getItem('viJoonLink_data');
let finalData;
try {
    finalData = savedData ? JSON.parse(savedData) : globalData;
} catch (e) {
    console.warn('LocalStorage data corrupted, using defaults:', e);
    localStorage.removeItem('viJoonLink_data');
    finalData = globalData;
}

// 브라우저 환경에서 전역 접근 가능하도록 노출
window.viJoonData = finalData;