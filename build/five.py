#!/usr/bin/env python3
# Five Programming Language Interpreter v1.0
# The evolution of Four - Made with even more love ❤️
# Real language implementation with tokenizer and parser

import sys
import os
import re
import json
import tempfile
import subprocess
import shutil
import zipfile
import platform
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Union

class TokenType(Enum):
    # Literals
    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"
    
    # Keywords
    PROJECT = "project"
    REQUIRE = "require"
    DEFINE = "define"
    CLASS = "class"
    FUNCTION = "function"
    
    # Operators
    DOT = "."
    EQUALS = "="
    LPAREN = "("
    RPAREN = ")"
    COMMA = ","
    COLON = ":"
    
    # Special
    NEWLINE = "NEWLINE"
    INDENT = "INDENT"
    DEDENT = "DEDENT"
    COMMENT = "COMMENT"
    EOF = "EOF"

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int

class FiveError(Exception):
    """Five errors with love"""
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"Error with love at line {line}, column {column}: {message}")

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens = []
        self.indent_stack = [0]
        self.stop_tokenizing = False  # Nueva bandera
        
        self.keywords = {
            'project': TokenType.PROJECT,
            'require': TokenType.REQUIRE,
            'define': TokenType.DEFINE,
            'class': TokenType.CLASS,
            'function': TokenType.FUNCTION,
        }
    
    def current_char(self) -> Optional[str]:
        if self.position >= len(self.source):
            return None
        return self.source[self.position]
    
    def peek_char(self, offset: int = 1) -> Optional[str]:
        peek_pos = self.position + offset
        if peek_pos >= len(self.source):
            return None
        return self.source[peek_pos]
    
    def advance(self):
        if self.position < len(self.source) and self.source[self.position] == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.position += 1
    
    def skip_whitespace(self):
        while self.current_char() and self.current_char() in ' \t':
            self.advance()
    
    def read_string(self) -> str:
        quote_char = self.current_char()
        self.advance()  # Skip opening quote
        value = ""
        
        while self.current_char() and self.current_char() != quote_char:
            if self.current_char() == '\\':
                self.advance()
                if self.current_char():
                    escape_chars = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"', "'": "'"}
                    value += escape_chars.get(self.current_char(), self.current_char())
                    self.advance()
            else:
                value += self.current_char()
                self.advance()
        
        if not self.current_char():
            raise FiveError("Unterminated string", self.line, self.column)
        
        self.advance()  # Skip closing quote
        return value
    
    def read_number(self) -> str:
        value = ""
        has_dot = False
        
        while self.current_char() and (self.current_char().isdigit() or self.current_char() == '.'):
            if self.current_char() == '.':
                if has_dot:
                    break
                has_dot = True
            value += self.current_char()
            self.advance()
        
        return value
    
    def read_identifier(self) -> str:
        value = ""
        while self.current_char() and (self.current_char().isalnum() or self.current_char() in '_'):
            value += self.current_char()
            self.advance()
        return value
    
    def read_comment(self) -> str:
        value = ""
        self.advance()  # Skip '>'
        while self.current_char() and self.current_char() != '\n':
            value += self.current_char()
            self.advance()
        return value.strip()
    
    def handle_indentation(self, line_start_pos: int) -> List[Token]:
        indent_tokens = []
        indent_level = 0
        pos = line_start_pos
        
        while pos < len(self.source) and self.source[pos] in ' \t':
            if self.source[pos] == ' ':
                indent_level += 1
            elif self.source[pos] == '\t':
                indent_level += 4  # Treat tab as 4 spaces
            pos += 1
        
        current_indent = self.indent_stack[-1] if self.indent_stack else 0
        
        if indent_level > current_indent:
            self.indent_stack.append(indent_level)
            indent_tokens.append(Token(TokenType.INDENT, "", self.line, self.column))
        elif indent_level < current_indent:
            while self.indent_stack and self.indent_stack[-1] > indent_level:
                self.indent_stack.pop()
                indent_tokens.append(Token(TokenType.DEDENT, "", self.line, self.column))
        
        return indent_tokens
    
    def tokenize(self) -> List[Token]:
        line_start = True
        
        while self.current_char() and not self.stop_tokenizing:
            start_line = self.line
            start_column = self.column
            
            # Handle indentation at line start
            if line_start:
                line_start = False
                line_start_pos = self.position
                self.skip_whitespace()
                
                # Skip empty lines and comments
                if self.current_char() in ['\n', None] or self.current_char() == '>':
                    if self.current_char() == '>':
                        comment_value = self.read_comment()
                        self.tokens.append(Token(TokenType.COMMENT, comment_value, start_line, start_column))
                    if self.current_char() == '\n':
                        self.advance()
                        line_start = True
                    continue
                
                # Handle indentation
                indent_tokens = self.handle_indentation(line_start_pos)
                self.tokens.extend(indent_tokens)
                continue
            
            char = self.current_char()
            
            if char == ' ' or char == '\t':
                self.skip_whitespace()
            elif char == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, char, start_line, start_column))
                self.advance()
                line_start = True
            elif char == '>':
                comment_value = self.read_comment()
                self.tokens.append(Token(TokenType.COMMENT, comment_value, start_line, start_column))
            elif char in '"\'':
                string_value = self.read_string()
                self.tokens.append(Token(TokenType.STRING, string_value, start_line, start_column))
                
                # Check if we just tokenized "main" after function
                if (len(self.tokens) >= 2 and 
                    self.tokens[-2].type == TokenType.FUNCTION and 
                    string_value == "main"):
                    self.stop_tokenizing = True
                    
            elif char.isdigit():
                number_value = self.read_number()
                self.tokens.append(Token(TokenType.NUMBER, number_value, start_line, start_column))
            elif char.isalpha() or char == '_':
                identifier = self.read_identifier()
                token_type = self.keywords.get(identifier, TokenType.IDENTIFIER)
                self.tokens.append(Token(token_type, identifier, start_line, start_column))
            elif char == '.':
                self.tokens.append(Token(TokenType.DOT, char, start_line, start_column))
                self.advance()
            elif char == '=':
                self.tokens.append(Token(TokenType.EQUALS, char, start_line, start_column))
                self.advance()
            elif char == '(':
                self.tokens.append(Token(TokenType.LPAREN, char, start_line, start_column))
                self.advance()
            elif char == ')':
                self.tokens.append(Token(TokenType.RPAREN, char, start_line, start_column))
                self.advance()
            elif char == ',':
                self.tokens.append(Token(TokenType.COMMA, char, start_line, start_column))
                self.advance()
            elif char == ':':
                self.tokens.append(Token(TokenType.COLON, char, start_line, start_column))
                self.advance()
            else:
                raise FiveError(f"Unexpected character: {char}", start_line, start_column)
        
        # Add final DEDENT tokens
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, "", self.line, self.column))
        
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens

class FiveInterpreter:
    def __init__(self):
        self.project = {
            'name': None,
            'version': '1.0',
            'platform': None,
            'description': 'Mi aplicacion de amor!'
        }
        self.required_modules = []
        self.shell_config = {
            'set': None,
            'run_commands': []
        }
        self.files_config = {
            'folders': [],
            'files': []
        }
        self.main_code = ""
        self.classes_found = {'shell': False}
        self.functions_found = {'main': False}
        
    def get_current_platform(self):
        system = platform.system().lower()
        return 'linux' if system in ('linux', 'darwin') else 'windows'

class Parser:
    def __init__(self, tokens: List[Token], original_source: str):
        self.tokens = tokens
        self.original_source = original_source
        self.position = 0
        self.interpreter = FiveInterpreter()
        self.in_main_code = False
    
    def current_token(self) -> Token:
        if self.position >= len(self.tokens):
            return self.tokens[-1]  # EOF token
        return self.tokens[self.position]
    
    def peek_token(self, offset: int = 1) -> Token:
        peek_pos = self.position + offset
        if peek_pos >= len(self.tokens):
            return self.tokens[-1]  # EOF token
        return self.tokens[peek_pos]
    
    def advance(self):
        if self.position < len(self.tokens) - 1:
            self.position += 1
    
    def expect_token(self, token_type: TokenType) -> Token:
        if self.current_token().type != token_type:
            raise FiveError(f"Expected {token_type.value}, got {self.current_token().value}", 
                          self.current_token().line, self.current_token().column)
        token = self.current_token()
        self.advance()
        return token
    
    def skip_newlines(self):
        while self.current_token().type == TokenType.NEWLINE:
            self.advance()
    
    def parse(self) -> FiveInterpreter:
        self.skip_newlines()
        
        while self.current_token().type != TokenType.EOF:
            if self.current_token().type == TokenType.COMMENT:
                self.advance()
            elif self.current_token().type == TokenType.PROJECT:
                self.parse_project_statement()
            elif self.current_token().type == TokenType.REQUIRE:
                self.parse_require_statement()
            elif self.current_token().type == TokenType.IDENTIFIER:
                self.parse_module_call()
            elif self.current_token().type == TokenType.DEFINE:
                self.parse_define_block()
            elif self.current_token().type == TokenType.NEWLINE:
                self.advance()
            else:
                if self.in_main_code:
                    # Collect everything else as main code
                    self.collect_main_code()
                else:
                    raise FiveError(f"Unexpected token: {self.current_token().value}",
                                  self.current_token().line, self.current_token().column)
        
        return self.interpreter
    
    def parse_project_statement(self):
        self.expect_token(TokenType.PROJECT)
        self.expect_token(TokenType.DOT)
        property_name = self.expect_token(TokenType.IDENTIFIER).value
        self.expect_token(TokenType.EQUALS)
        
        if self.current_token().type == TokenType.STRING:
            value = self.current_token().value
            self.advance()
        else:
            raise FiveError("Expected string value for project property",
                           self.current_token().line, self.current_token().column)
        
        if property_name in self.interpreter.project:
            self.interpreter.project[property_name] = value
        else:
            raise FiveError(f"Unknown project property: {property_name}",
                           self.current_token().line, self.current_token().column)
        
        self.skip_newlines()
    
    def parse_require_statement(self):
        self.expect_token(TokenType.REQUIRE)
        module_name = self.expect_token(TokenType.STRING).value
        self.interpreter.required_modules.append(module_name)
        self.skip_newlines()
    
    def parse_module_call(self):
        module_name = self.current_token().value
        self.advance()
        self.expect_token(TokenType.DOT)
        method_name = self.expect_token(TokenType.IDENTIFIER).value
        
        if module_name == "shell":
            if method_name == "set":
                self.expect_token(TokenType.EQUALS)
                value = self.expect_token(TokenType.STRING).value
                self.interpreter.shell_config['set'] = value
            elif method_name == "run":
                self.expect_token(TokenType.LPAREN)
                command = self.expect_token(TokenType.STRING).value
                self.expect_token(TokenType.RPAREN)
                self.interpreter.shell_config['run_commands'].append(command)
        elif module_name == "files":
            if method_name == "add":
                self.expect_token(TokenType.LPAREN)
                file_type = self.expect_token(TokenType.STRING).value
                self.expect_token(TokenType.COMMA)
                
                if file_type == "folder":
                    folder_name = self.expect_token(TokenType.STRING).value
                    print(f'Folder with name "{folder_name}" added')
                    self.interpreter.files_config['folders'].append(folder_name)
                    self.expect_token(TokenType.RPAREN)
                elif file_type == "file":
                    src_path = self.expect_token(TokenType.STRING).value
                    self.expect_token(TokenType.COMMA)
                    dest_path = self.expect_token(TokenType.STRING).value
                    print(f'File with name "{os.path.basename(dest_path)}" from local path "{src_path}" added to app folder {os.path.dirname(dest_path)}.')
                    self.interpreter.files_config['files'].append((src_path, dest_path))
                    self.expect_token(TokenType.RPAREN)
        
        self.skip_newlines()
    
    def parse_define_block(self):
        self.expect_token(TokenType.DEFINE)
        self.expect_token(TokenType.CLASS)
        class_name = self.expect_token(TokenType.STRING).value
        self.skip_newlines()
        self.expect_token(TokenType.INDENT)
        
        if class_name == "shell":
            self.interpreter.classes_found['shell'] = True
        
        # Parse function inside class
        self.expect_token(TokenType.FUNCTION)
        function_name = self.expect_token(TokenType.STRING).value
        self.skip_newlines()
        
        if function_name == "main":
            self.interpreter.functions_found['main'] = True
            # After function "main", we exit Five context completely
            # Consume the DEDENT from the function definition
            if self.current_token().type == TokenType.DEDENT:
                self.advance()
            # Now collect everything remaining as raw source code
            self.collect_raw_source_code()
    
    def collect_raw_source_code(self):
        # After function "main", take everything remaining from original source
        # Find the exact position after 'function "main"' in the source
        source_lines = self.original_source.split('\n')
        
        function_main_line = -1
        for i, line in enumerate(source_lines):
            if 'function "main"' in line:
                function_main_line = i
                break
        
        if function_main_line == -1:
            self.interpreter.main_code = ""
            return
        
        # Take all lines after the function "main" line
        main_code_lines = source_lines[function_main_line + 1:]
        
        # Join and preserve original formatting
        self.interpreter.main_code = '\n'.join(main_code_lines).strip()
        
        # Advance to EOF to finish parsing
        while self.current_token().type != TokenType.EOF:
            self.advance()

class FiveCompiler:
    def __init__(self):
        pass
    
    def compile_file(self, five_file: str):
        if not five_file.endswith('.five'):
            raise FiveError("File must have .five extension")
        
        try:
            with open(five_file, 'r', encoding='utf-8') as f:
                source = f.read()
        except FileNotFoundError:
            raise FiveError(f"File {five_file} not found")
        
        print(f"Compiling {five_file} to {five_file[:-5]}.app..")
        
        # Tokenize
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        # Parse
        parser = Parser(tokens, source)
        interpreter = parser.parse()
        
        # Validate
        self.validate_interpreter(interpreter)
        
        # Build app
        app_file = f"{interpreter.project['name']}.app"
        self.build_app(interpreter, app_file)
        
        print(f'Compilation done! you can run the Application with "five run {app_file}"')
        
    def validate_interpreter(self, interpreter: FiveInterpreter):
        if not interpreter.project['name']:
            raise FiveError("Missing project.name declaration")
        if not interpreter.project['platform']:
            raise FiveError("Missing project.platform declaration")
        if 'shell' not in interpreter.required_modules:
            raise FiveError("Missing require \"shell\"")
        if not interpreter.shell_config['set']:
            raise FiveError("Missing shell.set configuration")
        if not interpreter.classes_found['shell']:
            raise FiveError("Missing define class \"shell\"")
        if not interpreter.functions_found['main']:
            raise FiveError("Missing function \"main\" inside shell class")
        
        valid_platforms = ['linux', 'windows', 'all']
        if interpreter.project['platform'] not in valid_platforms:
            raise FiveError(f"Platform '{interpreter.project['platform']}' is not valid. Use: {', '.join(valid_platforms)}")
    
    def build_app(self, interpreter: FiveInterpreter, output_file: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create settings.json
            settings_data = {
                'project': interpreter.project['name'],
                'platform': interpreter.project['platform'],
                'run': interpreter.shell_config['set'],
                'description': interpreter.project['description'],
                'version': interpreter.project['version']
            }
            settings_file = os.path.join(temp_dir, 'settings.json')
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)
            
            # Create code.five-code
            code_file = os.path.join(temp_dir, 'code.five-code')
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(interpreter.main_code)
            
            # Create folders
            for folder in interpreter.files_config['folders']:
                os.makedirs(os.path.join(temp_dir, folder), exist_ok=True)
            
            # Copy files
            for src, dest in interpreter.files_config['files']:
                dest_path = os.path.join(temp_dir, dest)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src, dest_path)
            
            # Create .app file
            with open(output_file, 'wb') as app_file:
                app_file.write(b'LOVE-APP')
                import io
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(settings_file, 'settings.json')
                    zipf.write(code_file, 'code.five-code')
                    for folder_name, _, files in os.walk(temp_dir):
                        for file in files:
                            full_path = os.path.join(folder_name, file)
                            rel_path = os.path.relpath(full_path, temp_dir)
                            if rel_path not in ['settings.json', 'code.five-code']:
                                zipf.write(full_path, rel_path)
                zip_buffer.seek(0)
                app_file.write(zip_buffer.read())

class FiveRunner:
    def __init__(self):
        pass
    
    def get_current_platform(self):
        system = platform.system().lower()
        return 'linux' if system in ('linux', 'darwin') else 'windows'
    
    def run_app(self, app_file: str):
        if not app_file.endswith('.app'):
            raise FiveError("File must have .app extension")
        
        try:
            with open(app_file, 'rb') as f:
                header = f.read(8)
                if header != b'LOVE-APP':
                    raise FiveError("Invalid .app file (incorrect header)")
                zip_content = f.read()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, 'temp.zip')
                with open(zip_path, 'wb') as zip_file:
                    zip_file.write(zip_content)
                
                with zipfile.ZipFile(zip_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # Load settings
                settings_file = os.path.join(temp_dir, 'settings.json')
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # Check platform compatibility
                app_platform = settings.get('platform', 'all')
                current_platform = self.get_current_platform()
                if app_platform != 'all' and app_platform != current_platform:
                    raise FiveError(f"This application is for {app_platform}, but you're on {current_platform}")
                
                # Execute the code
                run_command = settings['run'].split()
                run_command.append('code.five-code')
                
                result = subprocess.run(run_command, capture_output=True, text=True, cwd=temp_dir)
                if result.stdout:
                    print(result.stdout, end='')
                if result.stderr:
                    print(result.stderr, end='', file=sys.stderr)
                return result.returncode
                
        except FileNotFoundError:
            raise FiveError(f"File {app_file} not found")
        except zipfile.BadZipFile:
            raise FiveError("Corrupted .app file")
        except json.JSONDecodeError:
            raise FiveError("Corrupted .app configuration")

def main():
    if len(sys.argv) < 2:
        print("Five Programming Language v1.0 - Made with even more love ❤️")
        print("Usage:")
        print("  five compile <file.five>     - Compile project")
        print("  five run <file.app>          - Execute application")
        print("  five version                 - Show version")
        return

    command = sys.argv[1]

    try:
        if command in ("-v", "--version", "version"):
            print("Five Programming Language v1.0 - Made with even more love ❤️")
            return

        elif command == "compile":
            if len(sys.argv) != 3:
                print("Error with love: Usage: five compile <file.five>")
                return
            five_file = sys.argv[2]
            compiler = FiveCompiler()
            compiler.compile_file(five_file)

        elif command == "run":
            if len(sys.argv) != 3:
                print("Error with love: Usage: five run <file.app>")
                return
            app_file = sys.argv[2]
            runner = FiveRunner()
            runner.run_app(app_file)

        else:
            print(f"Error with love: Command '{command}' not recognized")

    except FiveError as e:
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error with love: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
