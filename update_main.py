import re

with open('api/main.py', 'r') as f:
    content = f.read()

# Add get_current_user import
if 'from services.auth_service import get_current_user' not in content:
    content = content.replace('from routers.integrations import github', 'from routers.integrations import github\nfrom services.auth_service import get_current_user\nfrom fastapi import Depends')

# Add dependencies to include_router
def add_depends(router_name):
    global content
    old_str = f'app.include_router({router_name}.router)'
    new_str = f'app.include_router({router_name}.router, dependencies=[Depends(get_current_user)])'
    content = content.replace(old_str, new_str)

for r in ['notes', 'config', 'tags', 'skills', 'goals', 'gamification', 'personal_streaks', 'github', 'vault', 'ai', 'planning', 'websocket', 'export', 'stats']:
    add_depends(r)

with open('api/main.py', 'w') as f:
    f.write(content)
