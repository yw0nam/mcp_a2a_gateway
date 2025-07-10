#!/usr/bin/env node

const { spawn } = require('child_process');

// npx를 통해 전달된 추가 인수를 가져옵니다.
const args = process.argv.slice(2);

// pyproject.toml에 정의된 Python 스크립트를 실행합니다.
const command = 'uv';
const commandArgs = ['run', 'mcp-a2a-gateway', ...args];

console.log(`> Executing: ${command} ${commandArgs.join(' ')}`);

const pyProcess = spawn(command, commandArgs, {
    stdio: 'inherit', // 부모 프로세스(터미널)와 입출력을 공유합니다.
    shell: true
});

pyProcess.on('close', (code) => {
    if (code !== 0) {
        console.error(`Process exited with code ${code}`);
    }
});

pyProcess.on('error', (err) => {
    console.error('Failed to start subprocess.', err);
});

