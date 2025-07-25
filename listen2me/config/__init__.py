"""Simple YAML configuration loader for Listen2Me."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Listen2MeConfig:
    """Listen2Me configuration loader."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration loader.
        
        Args:
            config_path: Path to YAML config file. If None, looks for listen2me.yaml 
                        in current directory and parent directories.
        """
        self.config_file = Path(config_path)
        
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        logger.info(f"Loading configuration from: {self.config_file}")
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and parse YAML configuration file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not config:
                raise ValueError("Configuration file is empty")
            
            # Resolve relative paths
            self._resolve_paths(config)
            
            logger.info("Configuration loaded successfully")
            return config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
    
    def _resolve_paths(self, config: Dict[str, Any]) -> None:
        """Resolve relative paths in configuration relative to config file location."""
        config_dir = self.config_file.parent
        
        # Resolve Google credentials path
        if 'google_cloud' in config and 'credentials_path' in config['google_cloud']:
            creds_path = config['google_cloud']['credentials_path']
            if not os.path.isabs(creds_path):
                config['google_cloud']['credentials_path'] = str(config_dir / creds_path)
        
        # Resolve data directory
        if 'storage' in config and 'data_directory' in config['storage']:
            data_dir = config['storage']['data_directory']
            if not os.path.isabs(data_dir):
                config['storage']['data_directory'] = str(config_dir / data_dir)
        
        # Resolve log file path
        if 'logging' in config and 'file_path' in config['logging']:
            log_path = config['logging']['file_path']
            if not os.path.isabs(log_path):
                config['logging']['file_path'] = str(config_dir / log_path)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'google_cloud.language').
        
        Args:
            key_path: Dot-separated key path (e.g., 'google_cloud.credentials_path')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """Set configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to config value (e.g., 'google_cloud.language')
            value: Value to set
        """
        keys = key_path.split('.')
        config_dict = self.config
        
        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config_dict:
                config_dict[key] = {}
            config_dict = config_dict[key]
        
        # Set the final value
        config_dict[keys[-1]] = value
        logger.debug(f"Configuration key '{key_path}' set to: {value}")
    
    def get_google_credentials_path(self) -> str:
        """Get Google credentials path - CRASHES if not found."""
        creds_path = self.get('google_cloud.credentials_path')
        if not creds_path:
            raise ValueError("Google credentials path not configured in listen2me.yaml")
        
        creds_file = Path(creds_path)
        if not creds_file.exists():
            raise FileNotFoundError(f"Google credentials file not found: {creds_path}")
        
        return str(creds_file.absolute())
    
    def get_data_directory(self) -> str:
        """Get data directory path."""
        data_dir = self.get('storage.data_directory', 'data')
        return str(Path(data_dir).absolute())

