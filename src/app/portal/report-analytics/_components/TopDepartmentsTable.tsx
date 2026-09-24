import { Card } from "@/components/ui/Card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Row = { department_name: string; appointment_count: number; revenue: number };

type Props = { data: Row[]; className?: string };

/** Top Performing Departments -- a small ranked table (#, Department,
 * Appointments, Revenue), plain Table/TableRow/TableCell primitives
 * (components/ui/table.tsx) rather than the paginated DataTable, since this
 * list is always short (one row per department) and never needs sorting/
 * pagination/column-visibility. */
export function TopDepartmentsTable({ data, className }: Props) {
  return (
    <Card className={`p-space-4 ${className ?? ""}`}>
      <h3 className="text-label mb-space-4 text-ink-900 font-bold">Top Performing Departments</h3>
      {data.length === 0 ? (
        <p className="text-ink-400 text-[13px]">No department activity for the selected range.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Appointments</TableHead>
              <TableHead>Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row, i) => (
              <TableRow key={row.department_name}>
                <TableCell className="text-ink-400">{i + 1}</TableCell>
                <TableCell className="text-ink-900 font-semibold whitespace-normal">
                  {row.department_name}
                </TableCell>
                <TableCell>{row.appointment_count.toLocaleString()}</TableCell>
                <TableCell>₹{row.revenue.toLocaleString("en-IN")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}
