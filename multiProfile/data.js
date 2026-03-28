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
        },
        {
            "id": "proj-1774694020506",
            "title": "올인원 라이프 계산기",
            "description": "복리/적금, 대출 상환, 연봉 실수령액, 단위 변환, 디데이 등 생활 금융 계산기 모음",
            "tags": [],
            "url": "https://all-in-one-calculator-theta.vercel.app",
            "thumbnail": "https://ibb.co/84rL3b9P"
        }
    ],
    "socials": {
        "instagram": "https://www.instagram.com/vi.jooncoding/",
        "github": "https://github.com/JoonChun",
        "email": "mailto:jeonjun47@gmail.com"
    }
};

// --- LocalStorage Persistence Layer ---
const savedData = localStorage.getItem('viJoonLink_data');
let finalData;
try {
    finalData = savedData ? JSON.parse(savedData) : globalData;
} catch (e) {
    console.warn('LocalStorage data corrupted, using defaults:', e);
    localStorage.removeItem('viJoonLink_data');
    finalData = globalData;
}

window.viJoonData = finalData;