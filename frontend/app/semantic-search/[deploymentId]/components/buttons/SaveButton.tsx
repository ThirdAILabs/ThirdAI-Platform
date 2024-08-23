import React from "react";
import styled from "styled-components";
import { FaSave } from "react-icons/fa";
import { Button } from "@/components/ui/button";

const SaveIcon = styled(FaSave)`
    cursor: pointer;
    color: white;
    font-size: 20px;
`;

export default function SaveButton(props: {
    onClick: () => void;
}) {
    return (
        <Button style={{height: "100%"}} onClick={props.onClick}>
            <SaveIcon />
        </Button>
    );
}
