import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';

export default function AccessPage() {
  const userRole = "Global Admin";
  const roleDescription = "This role has read and write access to all team members and models.";

  // Sample data for the table
  const models = [
    { name: 'Model A', type: 'Private Model', access: [{ member: 'Alice', type: 'Owner' }, { member: 'Bob', type: 'Read' }] },
    { name: 'Model B', type: 'Protected Model', access: [{ member: 'Alice', type: 'Write' }, { member: 'Charlie', type: 'Read' }] },
    { name: 'Model C', type: 'Public Model', access: [{ member: 'Bob', type: 'Owner' }, { member: 'Charlie', type: 'Write' }] },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manage Access</CardTitle>
        <CardDescription>View all personnel and their access.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <h2 className="text-xl font-semibold">Your role is: {userRole}</h2>
          <p>Role description: {roleDescription}</p>
        </div>
        <table className="min-w-full bg-white">
          <thead>
            <tr>
              <th className="py-2 px-4 text-left">Model Name</th>
              <th className="py-2 px-4 text-left">Model Type</th>
              <th className="py-2 px-4 text-left">Access</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model, index) => (
              <tr key={index} className="border-t">
                <td className="py-2 px-4">{model.name}</td>
                <td className="py-2 px-4">{model.type}</td>
                <td className="py-2 px-4">
                  {model.access.map((access, accessIndex) => (
                    <div key={accessIndex}>
                      {access.member} ({access.type})
                    </div>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
