---
name: Bug Report
about: Report an issue with the Supabase MCP server
title: An issue with doing X when Y under conditions Z
labels: bug
assignees: ''

---

## ⚠️ IMPORTANT NOTE
The following types of reports will be closed immediately without investigation:
- Vague reports like "Something is not working" without clear explanations
- Issues missing reproduction steps or necessary context
- Reports without essential information (logs, environment details)
- Issues already covered in the README

Please provide complete information as outlined below.

## Describe the bug
A clear and concise description of what the bug is.

## Steps to Reproduce
1.
2.
3.

## Connection Details
- Connection type: (Local or Remote)
- Using password with special characters? (Yes/No)

## Screenshots
If applicable, add screenshots to help explain your problem.

## Logs
HIGHLY USEFUL: Attach server logs from:
- macOS/Linux: ~/.local/share/supabase-mcp/mcp_server.log
- Windows: %USERPROFILE%\.local\share\supabase-mcp\mcp_server.log

You can get the last 50 lines with:
```
tail -n 50 ~/.local/share/supabase-mcp/mcp_server.log
```

## Additional context
Add any other context about the problem here.

## Checklist
Mark completed items with an [x]:
- [ ] I've included the server logs
- [ ] I've checked the README troubleshooting section
- [ ] I've verified my connection settings are correct
