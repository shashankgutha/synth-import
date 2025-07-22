#!/usr/bin/env python3

import re

def process_k8s_secrets(config_content):
    """Process K8SSEC_ prefixed values and convert to Kubernetes ${} format"""
    
    # Process each pattern separately to avoid conflicts
    # Order is important - more specific patterns first
    processed_content = config_content
    
    # Pattern 1: Handle "'K8SSEC_name'" -> '${name}' (nested quotes)
    pattern1 = r'"\'K8SSEC_([A-Za-z0-9_.-]+)\'"'
    def replace1(match):
        secret_name = match.group(1)
        return f"'${{{secret_name}}}'"
    processed_content = re.sub(pattern1, replace1, processed_content)
    
    # Pattern 2: Handle "QK8SSEC_name" -> '${name}' (Q prefix in double quotes) - MUST be before regular "K8SSEC_"
    pattern2 = r'"QK8SSEC_([A-Za-z0-9_.-]+)"'
    def replace2(match):
        secret_name = match.group(1)
        return f"'${{{secret_name}}}'"
    processed_content = re.sub(pattern2, replace2, processed_content)
    
    # Pattern 3: Handle "K8SSEC_name" -> ${name} (double quotes) - MUST be after QK8SSEC_
    pattern3 = r'"K8SSEC_([A-Za-z0-9_.-]+)"'
    def replace3(match):
        secret_name = match.group(1)
        return f"${{{secret_name}}}"
    processed_content = re.sub(pattern3, replace3, processed_content)
    
    # Pattern 4: Handle 'K8SSEC_name' -> '${name}' (single quotes)
    pattern4 = r"'K8SSEC_([A-Za-z0-9_.-]+)'"
    def replace4(match):
        secret_name = match.group(1)
        return f"'${{{secret_name}}}'"
    processed_content = re.sub(pattern4, replace4, processed_content)
    
    # Pattern 5: Handle K8SSEC_name -> ${name} (unquoted) - MUST be last to avoid conflicts
    pattern5 = r'(?<!Q)K8SSEC_([A-Za-z0-9_.-]+)'
    def replace5(match):
        secret_name = match.group(1)
        return f"${{{secret_name}}}"
    processed_content = re.sub(pattern5, replace5, processed_content)
    
    return processed_content

# Test cases
test_cases = [
    ("K8SSEC_ES_USERNAME", "${ES_USERNAME}"),
    ('"K8SSEC_ES_USERNAME"', "${ES_USERNAME}"),
    ("K8SSEC_env.CLIENT_SEC", "${env.CLIENT_SEC}"),
    ("'K8SSEC_env.CLIENT_SEC'", "'${env.CLIENT_SEC}'"),
    ('"\'K8SSEC_env.CLIENT_SEC\'"', "'${env.CLIENT_SEC}'"),
    ('"QK8SSEC_env.CLIENT_SEC"', "'${env.CLIENT_SEC}'"),
    ("K8SSEC_any-thing.here123", "${any-thing.here123}"),
]

print("Testing K8S Secrets Processing:")
print("=" * 50)

all_passed = True
for i, (input_text, expected) in enumerate(test_cases, 1):
    result = process_k8s_secrets(input_text)
    status = "✅ PASS" if result == expected else "❌ FAIL"
    
    if result != expected:
        all_passed = False
    
    print(f"Test {i}: {status}")
    print(f"  Input:    {input_text}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
    print()

# Test with a complex YAML-like content
complex_test = '''
outputs:
  default:
    type: elasticsearch
    hosts:
      - K8SSEC_ES_HOST
    username: "'K8SSEC_env.ES_USERNAME'"
    password: "'K8SSEC_ES_PASSWORD'"
    api_key: K8SSEC_env.API_KEY
inputs:
  streams:
    - type: browser
      urls:
        - "https://K8SSEC_env.TEST_URL"
      schedule: '@every 1m'
      client.request.headers:
        Authorization: "QK8SSEC_env.AUTH_TOKEN"
        AuthorizationKey: "'K8SSEC_env.KEY_TOKEN'"
'''

print("Complex YAML Test:")
print("=" * 50)
print("Input:")
print(complex_test)
print("\nOutput:")
result = process_k8s_secrets(complex_test)
print(result)

print("=" * 50)
if all_passed:
    print("🎉 All basic tests PASSED!")
else:
    print("⚠️  Some tests FAILED!")