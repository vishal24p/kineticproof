# Remote build and deployment guide

1. Create public GitHub repository; push this documentation and sanitized application files, never secrets or private raw footage.
2. Connect repository to Codex Cloud. Set explicit setup commands for `uv`, Node and dependency install only after lockfiles are created. Enable smallest permissions needed. Confirm commands from cloud environment rather than relying on laptop setup.
3. Existing GStack/ECC on local Codex may not exist in cloud; verify, don't block development if missing. Context7 optional for current library docs; review MCP permissions.
4. Implement slices using cloud tasks and PR reviews. CI runs repeatable tests and static checks, but remote Codex session is NOT the hosted user-facing app.
5. Evaluate simple hosted web/API options for upload sizes, temporary files, request timeout, CPU cost and secure secrets. Choose platform based on evidence; record ADR and deploy only after approval.
6. Never pass personal recordings, secret API keys, billing information or private media through public repositories/logs. Set cleanup and costs before public demo.
