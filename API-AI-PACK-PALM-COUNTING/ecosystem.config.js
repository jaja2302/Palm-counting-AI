module.exports = {
    apps: [
      {
        name: "palm-counting-ai",
        script: "python",
        args: "-m uvicorn main:app --host 0.0.0.0 --port 8765",
        cwd: "C:/Dev/Palm-counting-AI/API-AI-PACK-PALM-COUNTING",
        interpreter: "none",
        autorestart: true,
        watch: false,
        max_memory_restart: "1G",
        env: {
          ENV: "production"
        }
      }
    ]
  };
  