import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3-coder-next:cloud')
SCRIPT_DIR = os.getenv('SCRIPT_DIR', './scripts')

# Create script directory if it doesn't exist
os.makedirs(SCRIPT_DIR, exist_ok=True)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Conversation memory for context-aware interactions
conversation_memory = {}


class AgentTools:
    """Tools that the AI agent can use"""
    
    @staticmethod
    async def execute_command(command: str) -> dict:
        """Execute a shell command"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            return {
                'success': process.returncode == 0,
                'output': stdout.decode('utf-8', errors='ignore'),
                'error': stderr.decode('utf-8', errors='ignore')
            }
        except Exception as e:
            return {'success': False, 'output': '', 'error': str(e)}
    
    @staticmethod
    async def write_file(filepath: str, content: str) -> dict:
        """Write content to a file"""
        try:
            abs_path = os.path.abspath(os.path.join(SCRIPT_DIR, filepath))
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w') as f:
                f.write(content)
            return {'success': True, 'path': abs_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def read_file(filepath: str) -> dict:
        """Read content from a file"""
        try:
            abs_path = os.path.abspath(os.path.join(SCRIPT_DIR, filepath))
            with open(abs_path, 'r') as f:
                content = f.read()
            return {'success': True, 'content': content}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def list_files(directory: str = '.') -> dict:
        """List files in a directory"""
        try:
            abs_path = os.path.abspath(os.path.join(SCRIPT_DIR, directory))
            files = os.listdir(abs_path)
            return {'success': True, 'files': files}
        except Exception as e:
            return {'success': False, 'error': str(e)}


async def chat_with_ollama(prompt, system_prompt=None, stream=False):
    """Send a request to Ollama"""
    url = f"{OLLAMA_API_URL}/api/chat"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": stream
    }
    
    print(f"[DEBUG] Request to Ollama - Model: {OLLAMA_MODEL}")
    
    try:
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data.get('message', {}).get('content', '')
                    return content
                else:
                    error_text = await response.text()
                    return f"Error {response.status}: {error_text}"
    except Exception as e:
        return f"Error: {str(e)}"


async def agentic_execute(task: str, ctx, max_steps=10):
    """
    Execute a task with multi-step reasoning and tool use (OpenClaw-like)
    """
    system_prompt = """You are an autonomous AI agent that can execute tasks by breaking them down into steps.

Available tools:
1. execute_command(command) - Run shell commands
2. write_file(filepath, content) - Create/write files
3. read_file(filepath) - Read file contents
4. list_files(directory) - List files in directory

For each task:
1. Break it down into clear steps
2. Use tools to accomplish each step
3. Verify results before proceeding
4. Report progress and final outcome

Format your response as JSON:
{
    "thinking": "Your reasoning about the task",
    "steps": [
        {
            "action": "tool_name",
            "params": {"param": "value"},
            "reason": "Why this step"
        }
    ],
    "final_answer": "Summary of what was accomplished"
}
"""
    
    await ctx.send(f"🤖 **Starting agentic task execution...**\nTask: _{task}_")
    
    prompt = f"Task: {task}\n\nBreak this down into executable steps and provide them in JSON format."
    
    response = await chat_with_ollama(prompt, system_prompt)
    
    if not response or response.startswith("Error"):
        await ctx.send(f"❌ Planning failed: {response}")
        return
    
    # Parse the AI's plan
    try:
        # Extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            plan = json.loads(response[json_start:json_end])
        else:
            raise ValueError("No JSON found in response")
        
        # Show the thinking process
        if 'thinking' in plan:
            await ctx.send(f"💭 **Thinking:** {plan['thinking'][:500]}")
        
        # Execute steps
        if 'steps' in plan:
            results = []
            for i, step in enumerate(plan['steps'][:max_steps], 1):
                action = step.get('action', '')
                params = step.get('params', {})
                reason = step.get('reason', '')
                
                await ctx.send(f"**Step {i}:** {reason}\n`{action}({params})`")
                
                # Execute the tool
                result = await execute_tool(action, params)
                results.append(result)
                
                if result.get('success'):
                    output = result.get('output', result.get('content', result.get('files', 'Success')))
                    output_preview = str(output)[:500]
                    await ctx.send(f"✅ Step {i} completed\n```\n{output_preview}\n```")
                else:
                    error = result.get('error', 'Unknown error')
                    await ctx.send(f"❌ Step {i} failed: {error}")
                    break
                
                await asyncio.sleep(0.5)  # Brief pause between steps
            
            # Show final answer
            if 'final_answer' in plan:
                await ctx.send(f"🎯 **Final Result:**\n{plan['final_answer']}")
        else:
            await ctx.send("⚠️ No executable steps found in plan")
            
    except json.JSONDecodeError:
        # Fallback: treat as direct execution
        await ctx.send("⚠️ Could not parse structured plan. Executing directly...")
        await direct_execute(task, ctx)
    except Exception as e:
        await ctx.send(f"❌ Execution error: {str(e)}")


async def execute_tool(tool_name: str, params: dict) -> dict:
    """Execute a tool with given parameters"""
    tools = AgentTools()
    
    if tool_name == 'execute_command':
        return await tools.execute_command(params.get('command', ''))
    elif tool_name == 'write_file':
        return await tools.write_file(params.get('filepath', ''), params.get('content', ''))
    elif tool_name == 'read_file':
        return await tools.read_file(params.get('filepath', ''))
    elif tool_name == 'list_files':
        return await tools.list_files(params.get('directory', '.'))
    else:
        return {'success': False, 'error': f'Unknown tool: {tool_name}'}


async def direct_execute(task: str, ctx):
    """Direct execution without multi-step planning"""
    system_prompt = "Generate only the code needed to complete this task. No explanations."
    
    # Determine language from task
    language = 'python' if any(word in task.lower() for word in ['python', 'script', 'calculate']) else 'bash'
    
    prompt = f"Write {language} code to: {task}"
    response = await chat_with_ollama(prompt, system_prompt)
    
    if not response or response.startswith("Error"):
        await ctx.send(f"❌ Code generation failed: {response}")
        return
    
    # Clean code
    code = response.strip()
    if code.startswith('```'):
        lines = code.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].startswith('```'):
            lines = lines[:-1]
        code = '\n'.join(lines)
    
    # Save and execute
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"task_{timestamp}.{'py' if language == 'python' else 'sh'}"
    filepath = os.path.join(SCRIPT_DIR, filename)
    
    with open(filepath, 'w') as f:
        f.write(code)
    
    if language == 'bash':
        os.chmod(filepath, 0o755)
    
    await ctx.send(f"📝 Generated code:\n```{language}\n{code[:1000]}\n```")
    
    # Execute
    abs_filepath = os.path.abspath(filepath)
    command = f"python3 {abs_filepath}" if language == 'python' else f"bash {abs_filepath}"
    
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode == 0:
        output = stdout.decode('utf-8', errors='ignore')
        await ctx.send(f"✅ **Executed successfully!**\n```\n{output[:1000]}\n```")
    else:
        error = stderr.decode('utf-8', errors='ignore')
        await ctx.send(f"❌ **Execution failed:**\n```\n{error[:500]}\n```")


@bot.event
async def on_ready():
    print(f'✅ {bot.user} has connected to Discord!')
    print(f'🤖 Model: {OLLAMA_MODEL}')
    print(f'📁 Script directory: {SCRIPT_DIR}')
    print(f'🔗 Ollama API: {OLLAMA_API_URL}')
    print(f'🧠 Agentic mode: Enabled')


@bot.command(name='task')
async def task_command(ctx, *, description: str):
    """
    Execute a task with agentic reasoning and multi-step execution
    Usage: !task Install a Python package and write a script that uses it
    """
    async with ctx.typing():
        await agentic_execute(description, ctx)


@bot.command(name='auto_execute')
async def auto_execute(ctx, language: str, *, description: str):
    """
    Generate and execute a script in one command
    Usage: !auto_execute python "Check disk space"
    """
    async with ctx.typing():
        system_prompt = f"""Generate only {language} code. No explanations, no markdown. Just the code."""
        
        prompt = f"Write {language} code to: {description}"
        
        await ctx.send(f"🤖 Generating {language} script...")
        
        response = await chat_with_ollama(prompt, system_prompt)
        
        if not response or response.startswith("Error"):
            await ctx.reply(f"❌ Failed to generate script: {response}")
            return
        
        # Clean up the code
        code = response.strip()
        if code.startswith('```'):
            lines = code.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            code = '\n'.join(lines)
        
        # Create the script file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"auto_exec_{timestamp}.{'py' if language == 'python' else 'sh'}"
        filepath = os.path.join(SCRIPT_DIR, filename)
        
        os.makedirs(SCRIPT_DIR, exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(code)
        
        if language == 'bash':
            os.chmod(filepath, 0o755)
        
        await ctx.send(f"✅ Script created: `{filename}`")
        
        # Show the generated code
        code_preview = code if len(code) <= 1500 else code[:1500] + "\n... (truncated)"
        await ctx.send(f"```{language}\n{code_preview}\n```")
        
        # Execute the script
        await ctx.send(f"⚡ Executing script...")
        
        abs_filepath = os.path.abspath(filepath)
        
        if language == 'python':
            command = f"python3 {abs_filepath}"
        else:
            command = f"bash {abs_filepath}"
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        
        result = {
            'returncode': process.returncode,
            'stdout': stdout.decode('utf-8', errors='ignore'),
            'stderr': stderr.decode('utf-8', errors='ignore')
        }
        
        # Display results
        embed = discord.Embed(
            title="📊 Execution Result",
            color=discord.Color.green() if result['returncode'] == 0 else discord.Color.red()
        )
        
        embed.add_field(name="Return Code", value=result['returncode'], inline=True)
        embed.add_field(name="Script", value=f"`{filename}`", inline=True)
        
        if result['stdout']:
            output = result['stdout'].strip()
            if len(output) > 1000:
                output = output[:1000] + "\n... (truncated)"
            embed.add_field(name="Output", value=f"```\n{output}\n```", inline=False)
        else:
            embed.add_field(name="Output", value="*(no output)*", inline=False)
        
        if result['stderr']:
            errors = result['stderr'].strip()
            if len(errors) > 500:
                errors = errors[:500] + "\n... (truncated)"
            embed.add_field(name="Errors", value=f"```\n{errors}\n```", inline=False)
        
        await ctx.reply(embed=embed)
        
        if result['returncode'] == 0:
            await ctx.send("✅ Script executed successfully!")
        else:
            await ctx.send("⚠️ Script completed with errors.")


@bot.command(name='chat')
async def chat_command(ctx, *, message: str):
    """
    Have a conversation with the AI (with memory)
    Usage: !chat What can you help me with?
    """
    user_id = ctx.author.id
    
    # Initialize conversation memory
    if user_id not in conversation_memory:
        conversation_memory[user_id] = []
    
    # Add user message to memory
    conversation_memory[user_id].append({"role": "user", "content": message})
    
    # Keep only last 10 messages
    if len(conversation_memory[user_id]) > 20:
        conversation_memory[user_id] = conversation_memory[user_id][-20:]
    
    async with ctx.typing():
        system_prompt = """You are an intelligent AI assistant that can help users with programming, system tasks, and automation.
You have the ability to execute code and commands when asked. Be helpful, concise, and practical."""
        
        # Build context from memory
        context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_memory[user_id][-6:]])
        
        response = await chat_with_ollama(message, system_prompt)
        
        if response and not response.startswith("Error"):
            # Add assistant response to memory
            conversation_memory[user_id].append({"role": "assistant", "content": response})
            
            # Split long responses
            if len(response) > 2000:
                chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.reply(response)
        else:
            await ctx.reply(f"❌ Error: {response}")


@bot.command(name='clear')
async def clear_command(ctx):
    """Clear your conversation memory"""
    user_id = ctx.author.id
    if user_id in conversation_memory:
        conversation_memory[user_id] = []
    await ctx.reply("✅ Conversation memory cleared!")


@bot.command(name='status')
async def status_command(ctx):
    """Check bot status"""
    async with ctx.typing():
        embed = discord.Embed(title="🔍 Bot Status", color=discord.Color.blue())
        
        # Check Ollama connection
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{OLLAMA_API_URL}/api/tags", timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m['name'] for m in data.get('models', [])]
                        embed.add_field(name="Ollama Status", value="✅ Connected", inline=False)
                        embed.add_field(name="Current Model", value=OLLAMA_MODEL, inline=False)
                        embed.add_field(name="Available Models", value=", ".join(models[:5]) if models else "None", inline=False)
                    else:
                        embed.add_field(name="Ollama Status", value=f"❌ Error (status {response.status})", inline=False)
        except Exception as e:
            embed.add_field(name="Ollama Status", value=f"❌ Cannot connect: {str(e)}", inline=False)
        
        embed.add_field(name="Script Directory", value=SCRIPT_DIR, inline=False)
        embed.add_field(name="Active Conversations", value=len(conversation_memory), inline=False)
        
        await ctx.reply(embed=embed)


@bot.command(name='info')
async def info_command(ctx):
    """Show help information"""
    embed = discord.Embed(
        title="🤖 OpenClaw-Style AI Bot",
        description="Autonomous AI agent with agentic reasoning and tool use",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🧠 Agentic Commands",
        value="`!task <description>` - Multi-step autonomous task execution\n"
              "`!chat <message>` - Conversational AI with memory\n"
              "`!auto_execute <lang> \"<desc>\"` - Direct code execution",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Available Tools",
        value="• Execute shell commands\n"
              "• Read/write files\n"
              "• List directories\n"
              "• Multi-step reasoning\n"
              "• Context-aware responses",
        inline=False
    )
    
    embed.add_field(
        name="📝 Examples",
        value='`!task Install requests library and write a script to fetch data from an API`\n'
              '`!task Create a backup of all Python files in this directory`\n'
              '`!chat What tasks can you help me automate?`\n'
              '`!auto_execute python "Calculate fibonacci numbers"`',
        inline=False
    )
    
    embed.add_field(
        name="💡 Features",
        value="✓ Multi-step task breakdown\n"
              "✓ Autonomous tool selection\n"
              "✓ Conversation memory\n"
              "✓ Error handling & recovery\n"
              "✓ Progress tracking",
        inline=False
    )
    
    embed.set_footer(text="Inspired by OpenClaw • Powered by Ollama")
    
    await ctx.reply(embed=embed)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN not found in .env file!")
        print("Please create a .env file with your Discord bot token.")
    else:
        print("🚀 Starting OpenClaw-style bot...")
        bot.run(DISCORD_TOKEN)