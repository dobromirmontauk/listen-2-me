"""Cross-platform keyboard input handling for the terminal UI."""

import sys
import threading
import time
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class KeyboardInputHandler:
    """Handle keyboard input in a cross-platform way."""
    
    def __init__(self, callback: Callable[[str], bool]):
        """Initialize keyboard handler.
        
        Args:
            callback: Function that takes a key and returns True to continue, False to quit
        """
        self.callback = callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the keyboard input handler."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._input_loop, daemon=True)
        self.thread.start()
        logger.info("Keyboard input handler started")
    
    def stop(self) -> None:
        """Stop the keyboard input handler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("Keyboard input handler stopped")
    
    def _input_loop(self) -> None:
        """Main input handling loop."""
        logger.info("Starting keyboard input loop")
        try:
            while self.running:
                try:
                    # Use a simple approach that works across platforms
                    key = self._get_key()
                    if key:
                        logger.info(f"Key detected: '{key}' (ord: {ord(key)})")
                        if not self.callback(key):
                            logger.info("Callback returned False, breaking input loop")
                            break
                    # Small delay to prevent busy waiting
                    time.sleep(0.05)
                except Exception as e:
                    logger.error(f"Error in input loop: {e}")
                    break
        except Exception as e:
            logger.error(f"Input loop error: {e}")
        logger.info("Keyboard input loop ended")
    
    def _get_key(self) -> Optional[str]:
        """Get a single keypress in a cross-platform way."""
        try:
            if sys.platform == "win32":
                return self._get_key_windows()
            else:
                return self._get_key_unix()
        except Exception as e:
            logger.error(f"Error getting key: {e}")
            return None
    
    def _get_key_windows(self) -> Optional[str]:
        """Get key on Windows."""
        try:
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8', errors='ignore')
                return key.lower()
        except ImportError:
            logger.warning("msvcrt not available for Windows key input")
        except Exception as e:
            logger.error(f"Windows key input error: {e}")
        
        return None
    
    def _get_key_unix(self) -> Optional[str]:
        """Get key on Unix/Linux/macOS."""
        try:
            import select
            import tty
            import termios
            
            # Check if input is available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                # Set terminal to raw mode to get single characters
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setraw(sys.stdin.fileno())
                    key = sys.stdin.read(1)
                    logger.debug(f"Raw key read: '{key}' (ord: {ord(key)})")
                    return key.lower()
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except ImportError:
            logger.warning("Unix terminal modules not available")
        except Exception as e:
            logger.error(f"Unix key input error: {e}")
        
        return None


class SimpleInputHandler:
    """Fallback simple input handler for environments where fancy input doesn't work."""
    
    def __init__(self, callback: Callable[[str], bool]):
        """Initialize simple handler.
        
        Args:
            callback: Function that takes a key and returns True to continue, False to quit
        """
        self.callback = callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the simple input handler."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._input_loop, daemon=True)
        self.thread.start()
        logger.info("Simple input handler started")
    
    def stop(self) -> None:
        """Stop the simple input handler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("Simple input handler stopped")
    
    def _input_loop(self) -> None:
        """Simple input loop using input()."""
        try:
            while self.running:
                try:
                    # Simple line-based input
                    print("\nPress Enter for commands, then type: (space/enter)=start/stop, s=stop, r=reset, q=quit")
                    user_input = input("> ").strip().lower()
                    
                    if not user_input:
                        user_input = " "  # Treat empty input as space
                    
                    key = user_input[0] if user_input else " "
                    
                    if not self.callback(key):
                        break
                        
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Simple input error: {e}")
                    break
        except Exception as e:
            logger.error(f"Simple input loop error: {e}")


def create_input_handler(callback: Callable[[str], bool]) -> object:
    """Create the best available input handler for the current platform.
    
    Args:
        callback: Function that takes a key and returns True to continue, False to quit
        
    Returns:
        An input handler instance
    """
    try:
        # Try the fancy keyboard handler first
        handler = KeyboardInputHandler(callback)
        return handler
    except Exception as e:
        logger.warning(f"Fancy keyboard handler not available: {e}")
        # Fall back to simple input handler
        return SimpleInputHandler(callback)