    def save_to_file(self, filepath: str) -> None:
        """Save recorded audio to WAV file.
        
        Args:
            filepath: Path to save the WAV file
        """
        if not self.audio_data:
            logger.warning("No audio data to save")
            return
        
        try:
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio_instance.get_sample_size(self.format) if self.pyaudio_instance else 2)
                wf.setframerate(self.sample_rate)
                
                # Write all audio data
                for chunk in self.audio_data:
                    wf.writeframes(chunk)
            
            logger.info(f"Audio saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            raise