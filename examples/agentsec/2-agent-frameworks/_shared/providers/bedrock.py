"""
AWS Bedrock provider with multiple authentication methods.

Supported auth methods:
- session_token (default): STS temporary credentials
- default: boto3 credential chain
- profile: Named AWS profile
- iam_role: Assume IAM role via STS
- access_key: Static access keys (not recommended for production)
"""

from typing import Any, Optional

from .base import BaseLLMProvider


class BedrockProvider(BaseLLMProvider):
    """
    AWS Bedrock provider supporting multiple authentication methods.
    
    Config structure:
        bedrock:
          model_id: anthropic.claude-3-haiku-20240307-v1:0
          region: us-east-1
          auth:
            method: session_token  # or default, profile, iam_role, access_key
            # For session_token:
            access_key_id: ${AWS_ACCESS_KEY_ID}
            secret_access_key: ${AWS_SECRET_ACCESS_KEY}
            session_token: ${AWS_SESSION_TOKEN}
            # For profile:
            profile: my-profile
            # For iam_role:
            role_arn: arn:aws:iam::123456789012:role/MyRole
            external_id: optional-external-id
    """
    
    AUTH_METHODS = ['session_token', 'default', 'profile', 'iam_role', 'access_key']
    
    def __init__(self, config: dict, llm_settings: Optional[dict] = None):
        super().__init__(config, llm_settings)
        self._bedrock_client = None
        self._session = None
    
    @property
    def model_id(self) -> str:
        """Return the Bedrock model ID."""
        return self.config.get('model_id', 'anthropic.claude-3-haiku-20240307-v1:0')
    
    @property
    def region(self) -> str:
        """Return the AWS region."""
        return self.config.get('region', 'us-east-1')
    
    def authenticate(self) -> None:
        """Set up AWS authentication based on config."""
        import boto3
        from botocore.config import Config as BotoConfig
        
        auth_config = self.config.get('auth', {})
        method = auth_config.get('method', 'session_token')
        
        if method not in self.AUTH_METHODS:
            raise ValueError(
                f"Unsupported auth method: {method}. "
                f"Supported: {self.AUTH_METHODS}"
            )
        
        # Configure boto with retries
        boto_config = BotoConfig(
            region_name=self.region,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        
        if method == 'default':
            # Use boto3's default credential chain
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                config=boto_config
            )
        
        elif method == 'profile':
            # Use named AWS profile
            profile = auth_config.get('profile', 'default')
            self._session = boto3.Session(profile_name=profile)
            self._bedrock_client = self._session.client(
                'bedrock-runtime',
                config=boto_config
            )
        
        elif method == 'iam_role':
            # Assume IAM role via STS
            role_arn = auth_config.get('role_arn')
            if not role_arn:
                raise ValueError("iam_role auth requires 'role_arn' in config")
            
            external_id = auth_config.get('external_id')
            
            sts = boto3.client('sts')
            assume_kwargs = {
                'RoleArn': role_arn,
                'RoleSessionName': 'agentsec-provider'
            }
            if external_id:
                assume_kwargs['ExternalId'] = external_id
            
            credentials = sts.assume_role(**assume_kwargs)['Credentials']
            
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                config=boto_config
            )
        
        elif method == 'session_token':
            # Use explicit session credentials (STS temp credentials)
            access_key_id = self._resolve_env(auth_config.get('access_key_id'))
            secret_access_key = self._resolve_env(auth_config.get('secret_access_key'))
            session_token = self._resolve_env(auth_config.get('session_token'))
            
            if not all([access_key_id, secret_access_key, session_token]):
                raise ValueError(
                    "session_token auth requires 'access_key_id', 'secret_access_key', "
                    "and 'session_token' in config"
                )
            
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token,
                config=boto_config
            )
        
        elif method == 'access_key':
            # Use static access keys (not recommended)
            access_key_id = self._resolve_env(auth_config.get('access_key_id'))
            secret_access_key = self._resolve_env(auth_config.get('secret_access_key'))
            
            if not all([access_key_id, secret_access_key]):
                raise ValueError(
                    "access_key auth requires 'access_key_id' and 'secret_access_key' in config"
                )
            
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=boto_config
            )
        
        self._authenticated = True
    
    def get_client(self) -> Any:
        """Return the boto3 bedrock-runtime client."""
        if not self._authenticated:
            self.authenticate()
        return self._bedrock_client
    
    # Framework adapters
    
    def get_langchain_llm(self) -> Any:
        """Return ChatBedrock instance for LangChain/LangGraph."""
        from langchain_aws import ChatBedrock
        
        # Ensure authenticated
        if not self._authenticated:
            self.authenticate()
        
        return ChatBedrock(
            model_id=self.model_id,
            region_name=self.region,
            model_kwargs={
                'temperature': self.temperature,
                'max_tokens': self.max_tokens,
            }
        )
    
    def get_crewai_llm(self) -> Any:
        """Return CrewAI LLM instance using native Bedrock integration.
        
        CrewAI has native Bedrock support via boto3's Converse API.
        """
        from crewai import LLM
        
        # Ensure authenticated first so boto3 credentials are set up
        if not self._authenticated:
            self.authenticate()
        
        # CrewAI native Bedrock integration uses bedrock/ prefix
        # and picks up credentials from boto3 session
        return LLM(
            model=f"bedrock/{self.model_id}",
            temperature=self.temperature,
        )
    
    def get_strands_model_id(self) -> str:
        """Return model ID for Strands agents."""
        # Strands uses the model ID directly for Bedrock
        return self.model_id
    
    def get_strands_model(self) -> Any:
        """Return None - Bedrock uses native model ID string with Strands."""
        # For Bedrock, Strands accepts the model_id string directly
        # and creates a BedrockModel internally
        return None
    
    def get_autogen_config(self) -> dict:
        """Return AutoGen/AG2 model client configuration for Bedrock.
        
        AG2 has native Bedrock support via api_type='bedrock'.
        Requires: pip install ag2[bedrock]
        """
        auth_config = self.config.get('auth', {})
        method = auth_config.get('method', 'default')
        
        config = {
            'model': self.model_id,
            'api_type': 'bedrock',
            'aws_region': self.region,
            'temperature': self.temperature,
        }
        
        # Add credentials based on auth method
        if method in ['session_token', 'access_key']:
            access_key = self._resolve_env(auth_config.get('access_key_id'))
            secret_key = self._resolve_env(auth_config.get('secret_access_key'))
            if access_key:
                config['aws_access_key'] = access_key
            if secret_key:
                config['aws_secret_key'] = secret_key
            if method == 'session_token':
                session_token = self._resolve_env(auth_config.get('session_token'))
                if session_token:
                    config['aws_session_token'] = session_token
        elif method == 'profile':
            profile = auth_config.get('profile', 'default')
            config['aws_profile_name'] = profile
        # For 'default' and 'iam_role', AG2 uses boto3's credential chain
        
        return config

