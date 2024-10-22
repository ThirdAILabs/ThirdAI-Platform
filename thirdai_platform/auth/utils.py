import os
from urllib.parse import urlparse

import fastapi


def get_hostname_from_url(url):
    try:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        return hostname
    except Exception as e:
        return f"Error parsing URL or resolving IP: {e}"


def create_realm(keycloak_admin, realm_name: str):
    """Create a new realm in Keycloak."""
    # Refer: https://www.keycloak.org/docs-api/21.1.1/rest-api/#_realmrepresentation
    payload = {
        "realm": realm_name,  # The name of the realm to create.
        "enabled": True,  # Enable the realm.
        "identityProviders": [],  # List of external identity providers, if any.
        "defaultRoles": ["user"],  # Default roles for users in this realm.
        "registrationAllowed": True,  # Allow user self-registration.
        "resetPasswordAllowed": True,  # Allow users to reset their password.
    }

    current_realms = [
        realms_metadata["realm"] for realms_metadata in keycloak_admin.get_realms()
    ]

    if realm_name not in current_realms:
        try:
            response = keycloak_admin.create_realm(
                payload
            )  # Create the realm if it doesn't exist.
            print(f"Realm '{realm_name}' created successfully: {response}")
        except Exception as e:
            print(f"Error creating realm '{realm_name}': {str(e)}")
            return None

    return realm_name


def create_client(
    keycloak_admin, client_name: str, redirect_uris: list, root_url: str, base_url: str
):
    """Create a new confidential client in Keycloak with the necessary permissions."""
    clients = keycloak_admin.get_clients()
    existing_client = next(
        (client for client in clients if client["clientId"] == client_name), None
    )

    if not existing_client:
        # Refer: https://www.keycloak.org/docs-api/21.1.1/rest-api/#_clientrepresentation
        # Configuration for the new client to be created.
        new_client = {
            "clientId": client_name,  # Unique client ID for the application.
            "enabled": True,  # Enable the client.
            "publicClient": True,  # Public client that doesn't require a secret for authentication.
            "redirectUris": redirect_uris,  # URIs where the client will redirect after authentication.
            "rootUrl": root_url,  # Root URL for the client application.
            "baseUrl": base_url,  # Base URL for the client application.
            "directAccessGrantsEnabled": False,  # Direct grants like password flow are disabled.
            "serviceAccountsEnabled": False,  # Service accounts are disabled.
            "standardFlowEnabled": True,  # Standard authorization code flow is enabled.
            "implicitFlowEnabled": False,  # Implicit flow is disabled.
            "fullScopeAllowed": False,  # Limit access to only allowed scopes.
            "defaultClientScopes": [
                "profile",
                "email",
                "openid",
                "roles",
            ],  # Default scopes for the client.
            "optionalClientScopes": [
                "offline_access",
                "microprofile-jwt",
            ],  # Optional scopes for the client.
            "protocolMappers": [
                {
                    "name": "audience resolve",  # Protocol mappers adjust tokens for clients.
                    "protocol": "openid-connect",  # The OIDC protocol used for authentication.
                    "protocolMapper": "oidc-audience-resolve-mapper",  # Mapper to add audience claim in tokens.
                    "consentRequired": False,  # No consent required for this mapper.
                    "config": {},  # Mapper configuration.
                }
            ],
            "webOrigins": redirect_uris,  # Allowed web origins for CORS.
        }

        keycloak_admin.create_client(new_client)  # Create the new client in the realm.
        print(f"Client '{client_name}' created successfully.")
    else:
        print(f"Client '{client_name}' already exists.")


identity_provider = os.getenv("IDENTITY_PROVIDER", "postgres")

keycloak_openid = None
keycloak_admin = None
thirdai_realm = "ThirdAI-Platform"  # A "realm" in Keycloak is an isolated group of users, roles, and clients.

# This is a helper object provided by FastAPI to extract the access token from a
# request. The paramter 'tokenURL' specifies which endpoint the user will use in
# the app to obtain the access token. When this is used in the fastapi.Depends
# clause in an endpoint (see `verify_access_token` below) it will find the
# 'Authorization' header in the request and check that the value of the header is
# 'Bearer <access token>' and then return the value of the access token within the
# header. It will return an 401 unauthorized code if the header is not found or
# is not properly formatted.
token_bearer = fastapi.security.OAuth2PasswordBearer(tokenUrl="/auth/token")

CREDENTIALS_EXCEPTION = fastapi.HTTPException(
    status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
    detail="Invalid access token.",
    # This header indicates what type of authentication would be required to access
    # the resource.
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/WWW-Authenticate
    headers={"WWW-Authenticate": "Bearer"},
)

IDENTITY_PROVIDER = os.getenv("IDENTITY_PROVIDER", "postgres").lower()


if IDENTITY_PROVIDER == "keycloak":
    from keycloak import (  # Keycloak SDK for managing users, roles, and OpenID authentication.
        KeycloakAdmin,
        KeycloakOpenID,
    )

    KEYCLOAK_SERVER_URL = os.getenv(
        "KEYCLOAK_SERVER_URL"
    )  # URL of the Keycloak server, needed for API access.

    client_name = "thirdai-login-client"

    public_hostname = get_hostname_from_url(
        os.getenv("PUBLIC_MODEL_BAZAAR_ENDPOINT")
    )  # Get the IP address from the public endpoint.
    private_hostname = get_hostname_from_url(
        os.getenv("PRIVATE_MODEL_BAZAAR_ENDPOINT")
    )  # Get the IP address from the private endpoint.

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_mail = os.getenv("ADMIN_MAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not KEYCLOAK_SERVER_URL:
        raise ValueError(
            "The environment variable 'KEYCLOAK_SERVER_URL' is required but was not found."
        )

    USE_SSL_IN_LOGIN = os.getenv("USE_SSL_IN_LOGIN", "False").lower() == "true"

    if USE_SSL_IN_LOGIN:
        # KeycloakAdmin allows managing Keycloak users, clients, and roles through admin API.
        # Refer: https://github.com/marcospereirampj/python-keycloak/blob/7cfad72a68346ca4cbcba69f9e8808091ae47daa/src/keycloak/keycloak_admin.py#L47
        keycloak_admin = KeycloakAdmin(
            server_url=KEYCLOAK_SERVER_URL,  # Admin API base URL.
            username=os.getenv(
                "KEYCLOAK_ADMIN_USER", "temp_admin"
            ),  # Admin username for API access.
            password=os.getenv(
                "KEYCLOAK_ADMIN_PASSWORD", "password"
            ),  # Admin password for API access.
            realm_name="master",  # The "master" realm is the default admin realm in Keycloak.
            verify="/model_bazaar/certs/traefik.crt",  # SSL certificate verification for secure connections.
            cert=(
                "/model_bazaar/certs/traefik.crt",
                "/model_bazaar/certs/traefik.key",
            ),
        )
    else:
        # Refer: https://github.com/marcospereirampj/python-keycloak/blob/7cfad72a68346ca4cbcba69f9e8808091ae47daa/src/keycloak/keycloak_admin.py#L47
        keycloak_admin = KeycloakAdmin(
            server_url=KEYCLOAK_SERVER_URL,
            username=os.getenv("KEYCLOAK_ADMIN_USER", "temp_admin"),
            password=os.getenv("KEYCLOAK_ADMIN_PASSWORD", "password"),
            realm_name="master",
            verify=False,  # SSL verification disabled for local or non-secure environments.
        )

    keycloak_user_id = keycloak_admin.get_user_id(admin_username)

    if keycloak_user_id:
        # Update user information such as email and verification status.
        keycloak_admin.update_user(
            keycloak_user_id, {"email": admin_mail, "emailVerified": True}
        )
    else:
        # Create a new Keycloak user with admin credentials if it does not exist.
        keycloak_user_id = keycloak_admin.create_user(
            {
                "username": admin_username,  # Username of the user to create.
                "email": admin_mail,  # Email of the user.
                "enabled": True,  # Enable the user account.
                "emailVerified": True,  # Mark email as verified.
                "credentials": [
                    {
                        "type": "password",  # Credential type, in this case, a password.
                        "value": admin_password,  # Password value.
                        "temporary": False,  # Password is permanent, not temporary.
                    }
                ],
            }
        )

    keycloak_roles = (
        keycloak_admin.get_realm_roles()
    )  # Get all available roles in the realm.
    role = next(
        (r for r in keycloak_roles if r["name"] == "admin"), None
    )  # Find the "admin" role.

    keycloak_admin.assign_realm_roles(
        keycloak_user_id, [role]
    )  # Assign the "admin" role to the user.

    new_realm_name = create_realm(
        keycloak_admin=keycloak_admin, realm_name=thirdai_realm
    )

    keycloak_admin.change_current_realm(
        new_realm_name
    )  # Change the active realm in Keycloak.

    create_client(
        keycloak_admin=keycloak_admin,
        client_name=client_name,
        root_url=KEYCLOAK_SERVER_URL,
        base_url="/login",
        redirect_uris=[
            f"http://{public_hostname}/*",
            f"https://{public_hostname}/*",
            f"http://{public_hostname}:80/*",
            f"https://{public_hostname}:80/*",
            f"http://{private_hostname}/*",
            f"https://{private_hostname}/*",
            f"http://{private_hostname}:80/*",
            f"https://{private_hostname}:80/*",
            f"http://localhost/*",
            f"https://localhost/*",
            f"http://localhost:80/*",
            f"https://localhost:80/*",
        ],
    )

    keycloak_openid = KeycloakOpenID(
        server_url=KEYCLOAK_SERVER_URL,
        client_id=client_name,
        realm_name=new_realm_name,  # Realm where the client resides.
    )

    if USE_SSL_IN_LOGIN:
        # Refer: https://github.com/marcospereirampj/python-keycloak/blob/7cfad72a68346ca4cbcba69f9e8808091ae47daa/src/keycloak/keycloak_openid.py#L65
        keycloak_openid = KeycloakOpenID(
            server_url=KEYCLOAK_SERVER_URL,
            client_id=client_name,
            realm_name=new_realm_name,
            verify="/model_bazaar/certs/traefik.crt",
            cert=(
                "/model_bazaar/certs/traefik.crt",
                "/model_bazaar/certs/traefik.key",
            ),
        )
    else:
        # Refer: https://github.com/marcospereirampj/python-keycloak/blob/7cfad72a68346ca4cbcba69f9e8808091ae47daa/src/keycloak/keycloak_openid.py#L65
        keycloak_openid = KeycloakOpenID(
            server_url=KEYCLOAK_SERVER_URL,
            client_id=client_name,
            realm_name=new_realm_name,
        )
