const fs = require('fs');

// Vercel 환경변수에서 API 키를 읽어 .env.js 생성
const apiKey = process.env.GEMINI_API_KEY || '';
const adminPass = process.env.ADMIN_PASS || '';

const content = `window.viJoonEnv = {
    GEMINI_API_KEY: "${apiKey}",
    ADMIN_PASS: "${adminPass}"
};
`;

fs.writeFileSync('.env.js', content);
console.log('.env.js generated' + (apiKey ? ' with API key.' : ' (no key set).'));
