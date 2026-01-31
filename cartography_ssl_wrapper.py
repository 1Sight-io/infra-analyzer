#!/usr/bin/env python3.12
"""
Cartography SSL Wrapper
Patches neo4j.GraphDatabase.driver to disable SSL verification before running Cartography.
This solves SSL certificate verification issues with Neo4j Aura.
"""

import sys
import os
from neo4j import GraphDatabase, TrustAll

# Save original driver function
_original_driver = GraphDatabase.driver

def patched_driver(uri, **kwargs):
    """Patched driver that disables SSL verification for secure URIs."""
    if uri.startswith(('bolt+s://', 'neo4j+s://')):
        # Convert secure URI to non-secure and manually configure encryption
        # This allows us to use TrustAll() for certificate validation
        if uri.startswith('bolt+s://'):
            uri = uri.replace('bolt+s://', 'bolt://')
        elif uri.startswith('neo4j+s://'):
            uri = uri.replace('neo4j+s://', 'neo4j://')
        
        # Enable encryption and disable certificate verification
        kwargs['encrypted'] = True
        kwargs['trusted_certificates'] = TrustAll()
        print(f"[SSL Wrapper] Disabling SSL verification for secure connection", file=sys.stderr)
    elif uri.startswith(('bolt+ssc://', 'neo4j+ssc://')):
        # Self-signed certificate variants
        if uri.startswith('bolt+ssc://'):
            uri = uri.replace('bolt+ssc://', 'bolt://')
        elif uri.startswith('neo4j+ssc://'):
            uri = uri.replace('neo4j+ssc://', 'neo4j://')
        
        kwargs['encrypted'] = True
        kwargs['trusted_certificates'] = TrustAll()
        print(f"[SSL Wrapper] Disabling SSL verification for self-signed certificate", file=sys.stderr)
    
    return _original_driver(uri, **kwargs)

# Monkey patch the driver
GraphDatabase.driver = patched_driver

# Now import and run cartography
if __name__ == '__main__':
    # Import cartography's main after patching
    from cartography.cli import CLI
    
    # Run cartography CLI
    cli = CLI()
    sys.exit(cli.main(sys.argv[1:]))
