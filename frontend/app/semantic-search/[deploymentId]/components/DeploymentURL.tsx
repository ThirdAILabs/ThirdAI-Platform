// ----------------------------------------------------------------------

export function createDeploymentUrl(deploymentId: string) {
    const hostname = process.env.NEXT_PUBLIC_DEPLOYMENT_BASE_URL;
    return `${hostname}/${deploymentId}`;
}

export function createTokenModelUrl(deploymentId: string) {
    const hostname = process.env.NEXT_PUBLIC_DEPLOYMENT_BASE_URL;
    return `${hostname}/${deploymentId}`;
}
